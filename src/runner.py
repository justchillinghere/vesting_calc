from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Optional
import pydantic

from rewards_calculators import calculate_vesting, calculate_deal_vesting
from models import (
    CCParameters,
    VestingParameters,
    CCCreationParameters,
    CCFailingParams,
    CCDealParameters,
)


def run_cc_simulation(cc_params: CCParameters):
    print("\033[92m" + "=" * 100 + "\033[0m")
    print("\033[92mCapacity Commitment (CC) Simulation Scenario\033[0m")
    print("\033[92m" + "=" * 100 + "\033[0m")

    # 1. Log initial scenario information
    cp = cc_params.creation_params
    fp = cc_params.failing_params
    dp = cc_params.deal_params

    print("\033[93mCC created with the following parameters:\033[0m")
    print(f"- Start Epoch: {cp.cc_start_epoch}")
    print(f"- End Epoch: {cp.cc_end_epoch}")
    print(f"- Total CUs: {cp.cu_amount}")
    print(f"- Staking Rate: {cp.staking_rate}%")
    print(f"- Reward per Epoch: {cc_params.vesting_params.reward_per_epoch}")
    print(f"- Vesting Period Count: {cc_params.vesting_params.vesting_period_count}")
    print(
        f"- Vesting Period Duration: {cc_params.vesting_params.vesting_period_duration}"
    )

    if fp.cc_fail_epoch:
        print(f"\033[91m\nCC will fail in Epoch {fp.cc_fail_epoch}\033[0m")

    if fp.slashed_epochs:
        print("\033[93m\nCUs will be slashed in the following Epochs:\033[0m")
        for cu, epochs in fp.slashed_epochs.items():
            print(f"- CU {cu}: Epochs {', '.join(map(str, epochs))}")

    if dp.amount_of_cu_to_move_to_deal > 0:
        print("\033[93m\nCC will participate in a Deal:\033[0m")
        print(f"- Deal Start Epoch: {dp.deal_start_epoch}")
        print(f"- Deal End Epoch: {dp.deal_end_epoch}")
        print(f"- CUs in Deal: {dp.amount_of_cu_to_move_to_deal}")
        print(f"- Price per CU in Deal (USD): ${dp.price_per_cu_in_offer_usd}")
        print(f"- FLT Price: ${dp.flt_price}")

    print(f"\033[93m\nCurrent Epoch: {cc_params.current_epoch}\033[0m")
    print("=" * 100)

    # 2. Run CC rewards calculation
    if fp.cc_fail_epoch and fp.cc_fail_epoch <= cc_params.current_epoch:
        print("\nCalculating CC Rewards:")
        print("CC has failed. No rewards will be earned.")
        cc_rewards = {
            "total_earned": 0,
            "unlocked": 0,
            "in_vesting": 0,
            "provider_rewards": 0,
            "staker_rewards": 0,
        }
    else:
        cc_rewards = calculate_vesting(cc_params)

    # 3. Run Deal vesting rewards calculation
    print("\nCalculating Deal Vesting Rewards:")
    if (
        dp.amount_of_cu_to_move_to_deal > 0 and dp.deal_start_epoch > 0
    ) and dp.deal_start_epoch <= cc_params.current_epoch:
        deal_rewards = calculate_deal_vesting(cc_params)
    else:
        print(
            "No active Deal or Deal hasn't started yet. No Deal rewards to calculate."
        )
        deal_rewards = {
            "total_earned_usd": 0,
            "total_earned_flt": 0,
            "unlocked_flt": 0,
            "in_vesting_flt": 0,
        }

    # 4. Print summary
    print("\n" + "=" * 100)
    print("\033[93mSimulation Summary:\033[0m")
    print(f"Total CC Rewards Earned: {cc_rewards['total_earned']:.4f}")
    print(f"CC Rewards Unlocked: {cc_rewards['unlocked']:.4f}")
    print(f"CC Rewards in Vesting: {cc_rewards['in_vesting']:.4f}")
    print(f"CC Provider Rewards: {cc_rewards['provider_rewards']:.4f}")
    print(f"CC Staker Rewards: {cc_rewards['staker_rewards']:.4f}")
    print(f"Deal Rewards Earned (USD): ${deal_rewards['total_earned_usd']:.4f}")
    print(f"Deal Rewards Earned (FLT): {deal_rewards['total_earned_flt']:.4f}")
    print(f"Deal Rewards Unlocked (FLT): {deal_rewards['unlocked_flt']:.4f}")
    print(f"Deal Rewards in Vesting (FLT): {deal_rewards['in_vesting_flt']:.4f}")
    print("=" * 100)

    return {"cc_rewards": cc_rewards, "deal_rewards": deal_rewards}


if __name__ == "__main__":
    cc_params = CCParameters(
        vesting_params=VestingParameters(
            vesting_period_count=5, vesting_period_duration=10, reward_per_epoch=1.0
        ),
        creation_params=CCCreationParameters(
            cu_amount=4, cc_start_epoch=5, cc_end_epoch=50, staking_rate=50
        ),
        failing_params=CCFailingParams(
            cc_fail_epoch=None, slashed_epochs={1: [12], 2: [9]}
        ),
        deal_params=CCDealParameters(
            deal_start_epoch=20,
            deal_end_epoch=40,
            amount_of_cu_to_move_to_deal=2,
            price_per_cu_in_offer_usd=10,
            flt_price=1,
        ),
        current_epoch=44,
    )

    simulation_results = run_cc_simulation(cc_params)
