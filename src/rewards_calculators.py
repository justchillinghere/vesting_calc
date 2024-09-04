from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Optional
import pydantic

from models import (
    CCParameters,
    VestingParameters,
    CCCreationParameters,
    CCFailingParams,
    CCDealParameters,
)


def group_consecutive_epochs(epochs):
    if not epochs:
        return []
    epochs = sorted(epochs)
    groups = []
    current_group = [epochs[0]]
    for epoch in epochs[1:]:
        if epoch == current_group[-1] + 1:
            current_group.append(epoch)
        else:
            groups.append(current_group)
            current_group = [epoch]
    groups.append(current_group)
    return groups


def calculate_period_rewards_for_cc(start_epoch, end_epoch, cc_params):
    vp = cc_params.vesting_params
    cp = cc_params.creation_params
    fp = cc_params.failing_params
    dp = cc_params.deal_params

    period_rewards = 0
    slashed_info = {}
    deal_epochs = set()

    for epoch in range(start_epoch, end_epoch):
        active_cus = cp.cu_amount

        # Check if it's a deal epoch
        if dp.deal_start_epoch <= epoch <= dp.deal_end_epoch:
            active_cus -= dp.amount_of_cu_to_move_to_deal
            deal_epochs.add(epoch)

        # Calculate slashed CUs for this epoch
        slashed_cus = sum(
            1
            for cu in range(1, cp.cu_amount + 1)
            if epoch in fp.slashed_epochs.get(cu, [])
        )

        # Calculate rewards for this epoch
        epoch_rewards = (active_cus - slashed_cus) * vp.reward_per_epoch
        period_rewards += epoch_rewards

        if slashed_cus > 0:
            slashed_info[epoch] = slashed_cus

    return period_rewards, slashed_info, deal_epochs


def calculate_vesting(cc_params: CCParameters):
    vp = cc_params.vesting_params
    cp = cc_params.creation_params
    fp = cc_params.failing_params
    dp = cc_params.deal_params

    print("=" * 80)
    print("\033[95m" + f"CC Vesting Calculation" + "\033[0m")
    print("=" * 80)

    last_epoch_to_count_rewards = min(cp.cc_end_epoch, cc_params.current_epoch)
    if fp.cc_fail_epoch:
        last_epoch_to_count_rewards = min(last_epoch_to_count_rewards, fp.cc_fail_epoch)

    # print(f"CC Start Epoch: {cp.cc_start_epoch}")
    # print(f"CC End Epoch: {cp.cc_end_epoch}")
    # print(f"Last Epoch to Count Rewards: {last_epoch_to_count_rewards}")
    # print(f"Total CUs: {cp.cu_amount}")
    # print(f"CUs in Deal: {dp.amount_of_cu_to_move_to_deal}")
    # print(f"CUs in CC: {cp.cu_amount - dp.amount_of_cu_to_move_to_deal}")
    # if fp.slashed_epochs:
    #     print(f"Slashed Epochs per CU: {fp.slashed_epochs}")
    # if fp.cc_fail_epoch:
    #     print(f"CC Fail Epoch: {fp.cc_fail_epoch}")
    # print(f"Reward per Epoch: {vp.reward_per_epoch}")
    # print(f"Staking Rate: {cp.staking_rate}%")
    # print("-" * 80)

    first_vesting_period_start = cp.cc_start_epoch - (
        cp.cc_start_epoch % vp.vesting_period_duration
    )
    last_vesting_period_start = last_epoch_to_count_rewards - (
        last_epoch_to_count_rewards % vp.vesting_period_duration
    )

    total_rewards_earned = 0
    unlocked_rewards = 0

    print("Vesting Periods Breakdown:")
    print(
        "{:<15} {:<15} {:<15} {:<15} {:<15} {:<20}".format(
            "Period Start",
            "Period End",
            "Rewards",
            "Unlocked %",
            "Unlocked Amount",
            "Slashed/Deal Info",
        )
    )
    print("-" * 95)

    for period_start in range(
        first_vesting_period_start,
        last_vesting_period_start + 1,
        vp.vesting_period_duration,
    ):
        period_end = period_start + vp.vesting_period_duration
        reward_start = max(period_start, cp.cc_start_epoch)
        reward_end = min(period_end, last_epoch_to_count_rewards)

        if reward_start >= reward_end:
            continue

        period_rewards, slashed_info, deal_epochs = calculate_period_rewards_for_cc(
            reward_start, reward_end, cc_params
        )

        total_rewards_earned += period_rewards

        periods_since_end = max(
            0, (cc_params.current_epoch - period_end) // vp.vesting_period_duration + 1
        )
        unlocked_fraction = min(periods_since_end / vp.vesting_period_count, 1)
        period_unlocked_rewards = period_rewards * unlocked_fraction
        unlocked_rewards += period_unlocked_rewards

        info_str = []
        if slashed_info:
            info_str.append(
                ", ".join(
                    [f"Slashed Epoch {e}: {c} CUs" for e, c in slashed_info.items()]
                )
            )

        deal_groups = group_consecutive_epochs(deal_epochs)
        if deal_groups:
            deal_intervals = [
                f"Deal Epochs {g[0]}-{g[-1]}" if len(g) > 1 else f"Deal Epoch {g[0]}"
                for g in deal_groups
            ]
            info_str.append(", ".join(deal_intervals))

        info_str = "; ".join(info_str)

        print(
            "{:<15} {:<15} {:<15.4f} {:<15.2%} {:<15.4f} {:<20}".format(
                period_start,
                period_end,
                period_rewards,
                unlocked_fraction,
                period_unlocked_rewards,
                info_str,
            )
        )

    rewards_in_vesting = max(0, total_rewards_earned - unlocked_rewards)

    # Calculate rewards for provider and staker
    provider_rewards = total_rewards_earned * (1 - cp.staking_rate / 100)
    staker_rewards = total_rewards_earned * (cp.staking_rate / 100)

    print("-" * 95)
    print(
        "\033[95m"
        + f"Results for CC Vesting, epoch {cc_params.current_epoch}"
        + "\033[0m"
    )
    print(f"Total Rewards Earned: {total_rewards_earned:.4f}")
    print(f"Unlocked Rewards: {unlocked_rewards:.4f}")
    print(f"Rewards in Vesting: {rewards_in_vesting:.4f}")
    print(f"Provider Rewards Total: {provider_rewards:.4f}")
    print(f"Staker Rewards Total: {staker_rewards:.4f}")
    print("=" * 80)

    return {
        "total_earned": total_rewards_earned,
        "unlocked": unlocked_rewards,
        "in_vesting": rewards_in_vesting,
        "provider_rewards": provider_rewards,
        "staker_rewards": staker_rewards,
    }


def round_to_precision(value, precision, decimal_places=4):
    rounded = round(value / precision, decimal_places)
    return rounded


def calculate_deal_vesting(cc_params: CCParameters, precision=1e7):
    dp = cc_params.deal_params
    cp = cc_params.creation_params

    precision = int(precision)
    reward_per_epoch_usd = int(dp.price_per_cu_in_offer_usd * precision)
    flt_price = int(dp.flt_price * precision)

    print("=" * 60)
    print("\033[95m" + f"Deal Rewards for Staker Vesting Calculation" + "\033[0m")
    print("=" * 60)

    last_epoch_to_count_rewards = min(dp.deal_end_epoch, cc_params.current_epoch)

    total_epochs_rewarded = (
        last_epoch_to_count_rewards - dp.deal_start_epoch + 1
    )  # Include the last epoch
    total_rewards_earned_usd = (
        total_epochs_rewarded * reward_per_epoch_usd * dp.amount_of_cu_to_move_to_deal
    )
    total_rewards_earned_flt = (
        total_rewards_earned_usd * precision // flt_price
    )  # Convert USD to FLT

    print(f"Deal Start Epoch: {dp.deal_start_epoch}")
    print(f"Deal End Epoch: {dp.deal_end_epoch}")
    print(f"Last Epoch to Count Rewards: {last_epoch_to_count_rewards}")
    print(f"Total Epochs Rewarded: {total_epochs_rewarded}")
    print(
        f"Deal Rewards Vesting periods count: {cc_params.vesting_params.vesting_period_count * cc_params.vesting_params.vesting_period_duration}"
    )
    print(f"CUs in Deal: {dp.amount_of_cu_to_move_to_deal}")
    print(
        f"Reward per CU per Epoch (USD): ${round_to_precision(reward_per_epoch_usd, precision)}"
    )
    print(f"FLT Price: ${round_to_precision(flt_price, precision)}")
    print(
        f"Total Rewards Earned (USD): ${round_to_precision(total_rewards_earned_usd, precision)}"
    )
    print(
        f"Total Rewards Earned (FLT): {round_to_precision(total_rewards_earned_flt, precision)}"
    )
    print("-" * 60)

    unlocked_rewards = 0
    print("Vesting Periods Breakdown:")
    print(
        "{:<15} {:<15} {:<15} {:<15} {:<15}".format(
            "Epoch",
            "Rewards (USD)",
            "Rewards (FLT)",
            "Unlocked %",
            "Unlocked Amount (FLT)",
        )
    )
    print("-" * 75)

    for work_epoch in range(dp.deal_start_epoch, last_epoch_to_count_rewards + 1):
        period_rewards_usd = reward_per_epoch_usd * dp.amount_of_cu_to_move_to_deal
        period_rewards_flt = (
            period_rewards_usd * (cp.staking_rate / 100) * precision // flt_price
        )

        periods_since_end = max(0, cc_params.current_epoch - work_epoch)
        unlocked_fraction = min(
            periods_since_end
            / (
                cc_params.vesting_params.vesting_period_count
                * cc_params.vesting_params.vesting_period_duration
            ),
            1,
        )
        period_unlocked_rewards = int(period_rewards_flt * unlocked_fraction)
        unlocked_rewards += period_unlocked_rewards

        print(
            "{:<15} {:<15.2f} {:<15.4f} {:<15.2%} {:<15.4f}".format(
                work_epoch,
                round_to_precision(period_rewards_usd, precision),
                round_to_precision(period_rewards_flt, precision),
                unlocked_fraction,
                round_to_precision(period_unlocked_rewards, precision),
            )
        )

    rewards_in_vesting = max(0, total_rewards_earned_flt - unlocked_rewards)

    print("-" * 75)
    print(
        "\033[95m"
        + f"Results for Deal Staker Rewards, epoch {cc_params.current_epoch}"
        + "\033[0m"
    )

    print(
        f"Total Unlocked Deal Staker Rewards (FLT): {round_to_precision(unlocked_rewards, precision)}"
    )
    print(
        f"Deal Staker Rewards Still in Vesting (FLT): {round_to_precision(rewards_in_vesting, precision)}"
    )
    print("=" * 60)

    return {
        "total_earned_usd": round_to_precision(total_rewards_earned_usd, precision),
        "total_earned_flt": round_to_precision(total_rewards_earned_flt, precision),
        "unlocked_flt": round_to_precision(unlocked_rewards, precision),
        "in_vesting_flt": round_to_precision(rewards_in_vesting, precision),
    }


# # Example usage
# cc_params = CCParameters(
#     vesting_params=VestingParameters(
#         vesting_period_count=10, vesting_period_duration=1, reward_per_epoch=1
#     ),
#     creation_params=CCCreationParameters(
#         cu_amount=32, cc_start_epoch=1, cc_end_epoch=30, staking_rate=50
#     ),
#     failing_params=CCFailingParams(cc_fail_epoch=None, slashed_epochs={}),
#     deal_params=CCDealParameters(
#         deal_start_epoch=10,
#         deal_end_epoch=20,
#         amount_of_cu_to_move_to_deal=5,
#         price_per_cu_in_offer_usd=10,
#         flt_price=1,
#     ),
#     current_epoch=20,
# )
