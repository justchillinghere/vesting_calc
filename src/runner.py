from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Optional
import pydantic
from utils import round_to_precision, group_consecutive_epochs

from rewards_calculators import (
    calculate_vesting,
    calculate_deal_vesting,
    calculate_expected_apr,
    calculate_average_apr,
)
from models import (
    TestScenarioParameters,
    VestingParameters,
    CCCreationParameters,
    CCFailingParams,
    CCDealParameters,
    NetworkParameters,
)


def run_cc_simulation(test_scenario_params: TestScenarioParameters):
    print("\033[92m" + "=" * 100 + "\033[0m")
    print("\033[92mCapacity Commitment (CC) Simulation Scenario\033[0m")
    print("\033[92m" + "=" * 100 + "\033[0m")

    # 1. Log initial scenario information
    cp = test_scenario_params.creation_params
    fp = test_scenario_params.failing_params
    dp = test_scenario_params.deal_params
    np = test_scenario_params.network_params

    print("\033[93mNetwork Parameters:\033[0m")
    print(f"- Epoch Duration: {np.epoch_duration} seconds")
    print(f"- USD Collateral per Unit: ${np.usd_collateral_per_unit}")
    print(f"- USD Target Revenue per Epoch: ${np.usd_target_revenue_per_epoch}")
    print(f"- FLT Price, USD: ${np.flt_usd_price}")

    print("\033[93mCC created with the following parameters:\033[0m")
    print(f"- Start Epoch: {cp.cc_start_epoch}")
    print(f"- End Epoch: {cp.cc_end_epoch}")
    print(f"- Total CUs: {cp.cu_amount}")
    print(f"- Staking Rate: {cp.staking_rate}%")

    print(
        f"- Vesting Period Count: {test_scenario_params.vesting_params.vesting_period_count}"
    )
    print(
        f"- Vesting Period Duration: {test_scenario_params.vesting_params.vesting_period_duration}"
    )

    calculate_expected_apr(test_scenario_params)

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

    print(f"\033[93m\nCurrent Epoch: {test_scenario_params.current_epoch}\033[0m")

    cc_rewards = calculate_vesting(test_scenario_params)

    # 3. Run Deal vesting rewards calculation
    print("\nCalculating Deal Vesting Rewards:")
    if (
        dp.amount_of_cu_to_move_to_deal > 0 and dp.deal_start_epoch > 0
    ) and dp.deal_start_epoch >= min(
        test_scenario_params.current_epoch,
        test_scenario_params.failing_params.cc_fail_epoch,
    ):
        deal_rewards = calculate_deal_vesting(test_scenario_params)
    else:
        print(
            "\033[91mNo active Deal is set or Deal hasn't started yet. No Deal rewards to calculate.\033[0m"
        )
        deal_rewards = {
            "total_earned_usd": 0,
            "total_earned_flt": 0,
            "unlocked_flt": 0,
            "in_vesting_flt": 0,
        }

    total_earned_flt = cc_rewards["total_earned"] + deal_rewards["total_earned_flt"]

    calculate_average_apr(total_earned_flt, test_scenario_params)

    # 4. Print summary
    print("\n" + "=" * 100)
    print("\033[93mSimulation Summary:\033[0m")
    print(f"Total CC Rewards Earned: {cc_rewards['total_earned']:.4f}")
    print(f"CC Rewards Unlocked: {cc_rewards['unlocked']:.4f}")
    print(f"CC Rewards in Vesting: {cc_rewards['in_vesting']:.4f}")
    print(f"CC Provider Rewards: {cc_rewards['provider_rewards']:.4f}")
    print(f"CC Staker Rewards: {cc_rewards['staker_rewards']:.4f}")

    if (
        dp.amount_of_cu_to_move_to_deal > 0 and dp.deal_start_epoch > 0
    ) and dp.deal_start_epoch <= test_scenario_params.current_epoch:
        print(f"Deal Rewards Earned (USD): ${deal_rewards['total_earned_usd']:.4f}")
        print(f"Deal Rewards Earned (FLT): {deal_rewards['total_earned_flt']:.4f}")
        print(f"Deal Rewards Unlocked (FLT): {deal_rewards['unlocked_flt']:.4f}")
        print(f"Deal Rewards in Vesting (FLT): {deal_rewards['in_vesting_flt']:.4f}")
    print("=" * 100)

    return {"cc_rewards": cc_rewards, "deal_rewards": deal_rewards}


if __name__ == "__main__":
    network_params = NetworkParameters(
        epoch_duration=86400,
        usd_collateral_per_unit=1,
        usd_target_revenue_per_epoch=1,
        flt_usd_price=1,
    )
    vesting_params = VestingParameters(
        vesting_period_count=5,
        vesting_period_duration=10,
    )
    creation_params = CCCreationParameters(
        cu_amount=1, cc_start_epoch=5, cc_end_epoch=50, staking_rate=100
    )
    failing_params = CCFailingParams(
        cc_fail_epoch=0, slashed_epochs={1: [10, 11, 12, 13, 14, 15]}
    )

    deal_params = CCDealParameters(
        deal_start_epoch=0,  # 0 means no deal
        deal_end_epoch=30,
        amount_of_cu_to_move_to_deal=1,
        price_per_cu_in_offer_usd=1,
    )

    test_scenario_params = TestScenarioParameters(
        network_params=network_params,
        vesting_params=vesting_params,
        creation_params=creation_params,
        failing_params=failing_params,
        deal_params=deal_params,
        current_epoch=44,
    )

    simulation_results = run_cc_simulation(test_scenario_params)
