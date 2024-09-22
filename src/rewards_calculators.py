from typing import Dict, List, Optional

from models import TestScenarioParameters, NetworkParameters
from utils import (
    round_to_precision,
    group_consecutive_epochs,
)


def calculate_expected_apr(test_scenario_params: TestScenarioParameters):
    np = test_scenario_params.network_params
    cp = test_scenario_params.creation_params
    precision = test_scenario_params.precision  # 10**7 by default

    collateral_flt = (
        cp.cu_amount * np.usd_collateral_per_unit * precision
    ) // np.flt_usd_price
    target_rewards_flt_per_epoch = (
        np.usd_target_revenue_per_epoch * precision
    ) // np.flt_usd_price

    seconds_in_year = 365 * 24 * 60 * 60
    epochs_in_year = seconds_in_year // np.epoch_duration
    year_revenue_flt = target_rewards_flt_per_epoch * epochs_in_year * cp.cu_amount

    expected_apr = (year_revenue_flt * precision) // collateral_flt
    # provider_expected_apr = (expected_apr * (100 - cp.staking_rate)) // 100
    staker_expected_apr = (expected_apr * cp.staking_rate) // 100

    print("=" * 80)
    print("\033[95m" + f"Expected APR Calculation" + "\033[0m")
    print("=" * 80)
    print(f"FLT Collateral: {round_to_precision(collateral_flt, precision)}")
    print(f"Year revenue in FLT: {round_to_precision(year_revenue_flt, precision)}")

    print(f"Total expected APR: {round_to_precision(expected_apr)} %")
    # print(f"Provider Expected APR: {round_to_precision(provider_expected_apr)} %")

    print(f"Staker Expected APR: {round_to_precision(staker_expected_apr)} %")
    print("=" * 80)

    return {
        "expected_apr_total": round_to_precision(expected_apr),
        "staker_expected_apr": round_to_precision(staker_expected_apr),
    }


def calculate_average_apr(
    total_reward: int, test_scenario_params: TestScenarioParameters
):
    cp = test_scenario_params.creation_params
    fp = test_scenario_params.failing_params
    np = test_scenario_params.network_params
    precision = test_scenario_params.precision  # 10**7 by default

    last_epoch_to_count_rewards = min(
        cp.cc_end_epoch,
        test_scenario_params.current_epoch,
    )
    if fp.cc_fail_epoch > 0:
        last_epoch_to_count_rewards = min(last_epoch_to_count_rewards, fp.cc_fail_epoch)

    total_epochs_rewarded = last_epoch_to_count_rewards - cp.cc_start_epoch

    collateral_flt = (
        cp.cu_amount * np.usd_collateral_per_unit * precision
    ) // np.flt_usd_price

    seconds_in_year = 365 * 24 * 60 * 60
    epochs_in_year = seconds_in_year // np.epoch_duration

    avg_reward = (total_reward * precision) // total_epochs_rewarded
    avg_reward_yearly = avg_reward * epochs_in_year
    avg_apr = (avg_reward_yearly * precision) // collateral_flt
    # provider_avg_apr = (avg_apr * (100 - cp.staking_rate)) // 100
    staker_avg_apr = (avg_apr * cp.staking_rate) // 100

    print("=" * 80)
    print("\033[95m" + f"Average APR Calculation" + "\033[0m")
    print("=" * 80)
    print(f"Total Reward: {total_reward}")
    print(f"Total epochs eligeble for rewards: {total_epochs_rewarded}")
    print(f"FLT Collateral: {round_to_precision(collateral_flt)}")
    print(f"Avg Reward per epoch: {round_to_precision(avg_reward)}")
    print(f"Avg Reward per year: {round_to_precision(avg_reward_yearly)}")
    print(f"Avg APR: {round_to_precision(avg_apr)} %")
    # print(f"Provider Avg APR: {round_to_precision(provider_avg_apr)} %")

    print(f"Staker Avg APR: {round_to_precision(staker_avg_apr)} %")
    print("=" * 80)

    return {
        "avg_apr_total": round_to_precision(avg_apr),
        "staker_avg_apr": round_to_precision(staker_avg_apr),
    }


def calculate_period_rewards_for_cc(
    start_epoch, end_epoch, test_scenario_params, precision=10**7
):
    np = test_scenario_params.network_params
    cp = test_scenario_params.creation_params
    fp = test_scenario_params.failing_params
    dp = test_scenario_params.deal_params

    flt_reward_per_epoch = (
        np.usd_target_revenue_per_epoch * precision // np.flt_usd_price
    )

    period_rewards = 0
    slashed_info = {}
    deal_epochs = set()

    for epoch in range(start_epoch, end_epoch):
        active_cus = cp.cu_amount

        # Check if it's a deal epoch
        if (dp.deal_start_epoch != 0 and dp.amount_of_cu_to_move_to_deal != 0) and (
            dp.deal_start_epoch <= epoch < dp.deal_end_epoch
        ):
            active_cus -= dp.amount_of_cu_to_move_to_deal
            deal_epochs.add(epoch)

        # Calculate slashed CUs for this epoch
        slashed_cus = sum(
            1
            for cu in range(1, cp.cu_amount + 1)
            if epoch in fp.slashed_epochs.get(cu, [])
        )

        # Calculate rewards for this epoch
        epoch_rewards = (active_cus - slashed_cus) * flt_reward_per_epoch
        period_rewards += epoch_rewards

        if slashed_cus > 0:
            slashed_info[epoch] = slashed_cus

    return period_rewards, slashed_info, deal_epochs


def calculate_vesting(test_scenario_params: TestScenarioParameters):
    vp = test_scenario_params.vesting_params
    cp = test_scenario_params.creation_params
    fp = test_scenario_params.failing_params
    withdrawal_epoch = test_scenario_params.withdrawal_epoch

    precision = test_scenario_params.precision  # 10**7 by default

    print("=" * 80)
    print("\033[95m" + f"CC Vesting Calculation" + "\033[0m")
    print("=" * 80)

    last_epoch_to_count_rewards = min(
        cp.cc_end_epoch, test_scenario_params.current_epoch
    )
    if fp.cc_fail_epoch > 0:
        last_epoch_to_count_rewards = min(last_epoch_to_count_rewards, fp.cc_fail_epoch)

    print(
        f"Rewards calculated from first active epoch {cp.cc_start_epoch} to the",
        end=" ",
    )
    if last_epoch_to_count_rewards == cp.cc_end_epoch:
        print(f"expiration epoch {cp.cc_end_epoch}")
    elif last_epoch_to_count_rewards == fp.cc_fail_epoch:
        print(f"efailure in epoch {fp.cc_fail_epoch}")
    elif last_epoch_to_count_rewards == test_scenario_params.current_epoch:
        print(f"current epoch {test_scenario_params.current_epoch}")

    print(
        f"Amount of epoch considered: {last_epoch_to_count_rewards - cp.cc_start_epoch} epochs"
    )

    first_vesting_period_start = cp.cc_start_epoch - (
        cp.cc_start_epoch % vp.vesting_period_duration
    )
    last_vesting_period_start = last_epoch_to_count_rewards - (
        last_epoch_to_count_rewards % vp.vesting_period_duration
    )

    total_rewards_earned = 0
    total_withdrawn = 0
    unlocked_rewards = 0

    print("Vesting Periods Breakdown:")
    print(
        "{:<15} {:<15} {:<15} {:<15} {:<15} {:<20}".format(
            "Period Start",
            "Period End",
            "Rewards",
            "Unlocked %",
            "Unlocked Amount",
            "Withdrawn Amount",
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
            reward_start,
            reward_end,
            test_scenario_params,
            precision=precision,
        )

        total_rewards_earned += period_rewards

        periods_since_end = max(
            0,
            (test_scenario_params.current_epoch - period_end)
            // vp.vesting_period_duration
            + 1,
        )
        unlocked_fraction_current = min(
            (periods_since_end * precision) // vp.vesting_period_count, precision
        )

        period_unlocked_rewards = (
            period_rewards * unlocked_fraction_current
        ) // precision

        period_withdrawn = 0
        if withdrawal_epoch > 0 and withdrawal_epoch >= period_start:
            periods_since_end_withdrawn = max(
                0,
                (withdrawal_epoch - period_end) // vp.vesting_period_duration + 1,
            )
            unlocked_fraction_withdrawn = min(
                (periods_since_end_withdrawn * precision) // vp.vesting_period_count,
                precision,
            )
            period_withdrawn = unlocked_fraction_withdrawn * period_rewards // precision

        total_withdrawn += period_withdrawn
        unlocked_rewards += period_unlocked_rewards - period_withdrawn

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
            "{:<15} {:<15} {:<15} {:<15.2%} {:<15} {:<15} {:<20}".format(
                period_start,
                period_end,
                round_to_precision(period_rewards),
                round_to_precision(unlocked_fraction_current),
                round_to_precision(period_unlocked_rewards),
                round_to_precision(period_withdrawn),
                info_str,
            )
        )

    rewards_in_vesting = max(
        0, total_rewards_earned - unlocked_rewards - total_withdrawn
    )
    to_claim = unlocked_rewards

    provider_rewards = (total_rewards_earned * (100 - cp.staking_rate) * precision) // (
        100 * precision
    )
    staker_rewards = (total_rewards_earned * cp.staking_rate * precision) // (
        100 * precision
    )

    print("-" * 110)
    print(
        "\033[95m"
        + f"Results for CC Vesting, epoch {test_scenario_params.current_epoch}"
        + "\033[0m"
    )
    print(f"Total Rewards Earned: {round_to_precision(total_rewards_earned)}")
    print(f"Total Withdrawn: {round_to_precision(total_withdrawn)}")
    print(f"Available for Withdrawal: {round_to_precision(to_claim)}")
    print(f"Rewards in Vesting: {round_to_precision(rewards_in_vesting)}")
    print(
        f"Check if sum is correct: {round_to_precision(total_withdrawn + to_claim + rewards_in_vesting)}"
    )
    print(f"Provider Rewards Total: {round_to_precision(provider_rewards)}")
    if cp.staking_rate > 0:
        print(f"Staker Rewards Total: {round_to_precision(staker_rewards)}")
    print("=" * 110)

    return {
        "total_earned": round_to_precision(total_rewards_earned),
        "total_withdrawn": round_to_precision(total_withdrawn),
        "to_claim": round_to_precision(to_claim),
        "in_vesting": round_to_precision(rewards_in_vesting),
        "provider_rewards": round_to_precision(provider_rewards),
        "staker_rewards": round_to_precision(staker_rewards),
    }


def calculate_deal_vesting(test_scenario_params: TestScenarioParameters):
    np = test_scenario_params.network_params
    dp = test_scenario_params.deal_params
    cp = test_scenario_params.creation_params
    fp = test_scenario_params.failing_params
    withdrawal_epoch = test_scenario_params.withdrawal_epoch

    precision = test_scenario_params.precision  # 10**7 by default
    reward_per_epoch_usd = int(dp.price_per_cu_in_offer_usd * precision)
    flt_price = int(np.flt_usd_price * precision)

    print("=" * 60)
    print("\033[95m" + f"Deal Rewards for Staker Vesting Calculation" + "\033[0m")
    print("=" * 60)

    last_epoch_to_count_rewards = min(
        dp.deal_end_epoch, test_scenario_params.current_epoch
    )
    if fp.cc_fail_epoch > 0:
        last_epoch_to_count_rewards = min(last_epoch_to_count_rewards, fp.cc_fail_epoch)

    total_epochs_rewarded = (
        last_epoch_to_count_rewards - dp.deal_start_epoch
    )  # Include the last epoch

    total_rewards_earned_usd = (
        total_epochs_rewarded
        * dp.price_per_cu_in_offer_usd
        * dp.amount_of_cu_to_move_to_deal
        * precision
    )
    total_rewards_earned_flt = total_rewards_earned_usd // np.flt_usd_price

    print(f"Deal Start Epoch: {dp.deal_start_epoch}")
    print(f"Deal End Epoch: {dp.deal_end_epoch}")
    print(f"Last Epoch to Count Rewards: {last_epoch_to_count_rewards}")
    print(f"Total Epochs Rewarded: {total_epochs_rewarded}")
    print(
        f"Deal Rewards Vesting periods count: {test_scenario_params.vesting_params.vesting_period_count * test_scenario_params.vesting_params.vesting_period_duration}"
    )
    print(f"CUs in Deal: {dp.amount_of_cu_to_move_to_deal}")
    print(f"Reward per CU per Epoch (USD): ${round_to_precision(reward_per_epoch_usd)}")
    print(
        f"Total Rewards Earned (USD): ${round_to_precision(total_rewards_earned_usd)}"
    )
    print(
        f"Total Rewards Earned (FLT): {round_to_precision(total_rewards_earned_flt, precision)}"
    )
    print(f"Staking Rate: {cp.staking_rate}%")
    print("-" * 60)

    unlocked_rewards = 0
    total_withdrawn = 0
    print("Vesting Periods Breakdown:")
    print(
        "{:<15} {:<15} {:<15} {:<15} {:<15} {:<15}".format(
            "Epoch",
            "Rewards (USD)",
            "Rewards (FLT)",
            "Unlocked %",
            "Unlocked Amount (FLT)",
            "Withdrawn Amount (FLT)",
        )
    )
    print("-" * 95)

    for work_epoch in range(dp.deal_start_epoch, last_epoch_to_count_rewards):
        period_rewards_usd = reward_per_epoch_usd * dp.amount_of_cu_to_move_to_deal
        period_rewards_flt = (
            period_rewards_usd * (cp.staking_rate * precision / 100) // flt_price
        )

        periods_since_end = max(0, test_scenario_params.current_epoch - work_epoch)
        unlocked_fraction = min(
            (periods_since_end * precision)
            // (
                test_scenario_params.vesting_params.vesting_period_count
                * test_scenario_params.vesting_params.vesting_period_duration
            ),
            precision,
        )

        period_unlocked_rewards = period_rewards_flt * unlocked_fraction // precision

        period_withdrawn = 0
        if withdrawal_epoch > 0 and withdrawal_epoch > work_epoch:
            periods_since_end_withdraw = max(0, withdrawal_epoch - work_epoch)
            unlocked_fraction_withdrawn = min(
                (periods_since_end_withdraw * precision)
                // (
                    test_scenario_params.vesting_params.vesting_period_count
                    * test_scenario_params.vesting_params.vesting_period_duration
                ),
                precision,
            )
            period_withdrawn = (
                unlocked_fraction_withdrawn * period_rewards_flt
            ) // precision

        total_withdrawn += period_withdrawn
        unlocked_rewards += period_unlocked_rewards - period_withdrawn

        print(
            "{:<15} {:<15.2f} {:<15.4f} {:<15.2%} {:<15.4f} {:<15.4f}".format(
                work_epoch,
                round_to_precision(period_rewards_usd),
                round_to_precision(period_rewards_flt),
                round_to_precision(unlocked_fraction),
                round_to_precision(period_unlocked_rewards),
                round_to_precision(period_withdrawn),
            )
        )

    rewards_in_vesting = max(
        0, total_rewards_earned_flt - unlocked_rewards - total_withdrawn
    )
    available_for_withdrawal = unlocked_rewards

    print("-" * 90)
    print(
        "\033[95m"
        + f"Results for Deal Staker Rewards, epoch {test_scenario_params.current_epoch}"
        + "\033[0m"
    )

    print(
        f"Total Rewards Earned (FLT): {round_to_precision(total_rewards_earned_flt, precision)}"
    )
    print(f"Total Withdrawn (FLT): {round_to_precision(total_withdrawn, precision)}")
    print(
        f"Available for Withdrawal (FLT): {round_to_precision(available_for_withdrawal, precision)}"
    )
    print(
        f"Rewards Still in Vesting (FLT): {round_to_precision(rewards_in_vesting, precision)}"
    )
    print("=" * 60)

    return {
        "total_earned_usd": round_to_precision(total_rewards_earned_usd, precision),
        "total_earned_flt": round_to_precision(total_rewards_earned_flt, precision),
        "total_withdrawn": round_to_precision(total_withdrawn, precision),
        "to_claim": round_to_precision(available_for_withdrawal, precision),
        "in_vesting": round_to_precision(rewards_in_vesting, precision),
    }
