import json
from typing import List, Dict, Any, Union
from models import TestScenarioParameters
from runner import run_cc_simulation


from models import (
    TestScenarioParameters,
    VestingParameters,
    CCCreationParameters,
    CCFailingParams,
    CCDealParameters,
    NetworkParameters,
)


def load_scenarios_from_json(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r") as json_file:
        scenarios = json.load(json_file)
    return scenarios


def run_multiple_scenarios(
    scenarios: Union[List[Dict[str, Any]], str], output_file: str
):
    if isinstance(scenarios, str):
        # If scenarios is a string, assume it's a file path and load from JSON
        scenarios = load_scenarios_from_json(scenarios)

    results = []

    for i, scenario in enumerate(scenarios):
        # Create parameter objects
        network_params = NetworkParameters(
            **{k: v for k, v in scenario.items() if k in NetworkParameters.model_fields}
        )
        vesting_params = VestingParameters(
            **{k: v for k, v in scenario.items() if k in VestingParameters.model_fields}
        )
        creation_params = CCCreationParameters(
            **{
                k: v
                for k, v in scenario.items()
                if k in CCCreationParameters.model_fields
            }
        )
        failing_params = CCFailingParams(
            **{k: v for k, v in scenario.items() if k in CCFailingParams.model_fields}
        )
        deal_params = CCDealParameters(
            **{k: v for k, v in scenario.items() if k in CCDealParameters.model_fields}
        )

        # Create TestScenarioParameters object
        params = TestScenarioParameters(
            network_params=network_params,
            vesting_params=vesting_params,
            creation_params=creation_params,
            failing_params=failing_params,
            deal_params=deal_params,
            current_epoch=scenario["current_epoch"],
            precision=scenario.get("precision", 10**7),
            withdrawal_epoch=scenario.get("withdrawal_epoch", 0),
        )

        print(f"Running scenario {i+1}...")
        # Run simulation
        simulation_result = run_cc_simulation(params)

        # Combine input parameters and results
        flattened_params = {}
        for key, value in params.model_dump().items():
            if isinstance(value, dict):
                flattened_params.update(value)
            else:
                flattened_params[key] = value

        result = {
            f"case_{i}": {"input": flattened_params, "result": {**simulation_result}}
        }
        results.append(result)

        # Write current results to JSON
        with open(output_file, "w") as json_file:
            json.dump(results, json_file, indent=2)

        print(f"Results for scenario {i+1} written to {output_file}")
        input("Press Enter to continue to the next scenario...")

    print(f"All scenarios completed. Final results are in {output_file}")


if __name__ == "__main__":

    std_scenario = {
        "epoch_duration": 86400,
        "usd_collateral_per_unit": 1,
        "usd_target_revenue_per_epoch": 1,
        "flt_usd_price": 1,
        "vesting_period_count": 5,
        "vesting_period_duration": 10,
        "cu_amount": 10,
        "cc_start_epoch": 5,
        "cc_end_epoch": 50,
        "staking_rate": 100,
        "cc_fail_epoch": 0,
        "slashed_epochs": {},
        "deal_start_epoch": 0,
        "deal_end_epoch": 30,
        "amount_of_cu_to_move_to_deal": 0,
        "price_per_cu_in_offer_usd": 1,
        "current_epoch": 44,
        "withdrawal_epoch": 0,
    }

    scenarios = [
        ## To check APR calculation
        # APR calculation scenarios
        {**std_scenario, "staking_rate": 100},  # Delegation Rate = 100%
        {**std_scenario, "staking_rate": 70},  # Delegation Rate = 70%
        {**std_scenario, "staking_rate": 0},  # Delegation Rate = 0%
        ## Withdrawal scenarios
        {**std_scenario, "withdrawal_epoch": 30},
        {**std_scenario, "withdrawal_epoch": 44},
        {**std_scenario, "withdrawal_epoch": 7},
        # To check slashing only
        {
            **std_scenario,
            "max_fail_ratio": 5,
            "slashed_epochs": {1: [10, 15, 25], 2: [5, 20, 30], 3: [39, 40]},
        },
        ## To check fail
        {
            **std_scenario,
            "cc_fail_epoch": 30,
            "max_fail_ratio": 2,
        },
        # To check fail and withdrawal
        {
            **std_scenario,
            "cc_fail_epoch": 30,
            "max_fail_ratio": 2,
            "withdrawal_epoch": 25,
        },
        # To check Deal participation, no withdrawal and fail
        {
            **std_scenario,
            "max_fail_ratio": 5,
            "deal_start_epoch": 20,
            "deal_end_epoch": 40,
            "amount_of_cu_to_move_to_deal": std_scenario["cu_amount"] // 2,
        },  ## Move half of the CUs to deal
        {
            **std_scenario,
            "deal_start_epoch": 20,
            "deal_end_epoch": 40,
            "amount_of_cu_to_move_to_deal": std_scenario["cu_amount"] // 2,
            "withdrawal_epoch": 37,
        },  ## Move half of the CUs to deal and withdraw during deal
        # To check Deal participation and fail
        {
            **std_scenario,
            "cc_fail_epoch": 35,
            "max_fail_ratio": 1,
            "slashed_epochs": {
                (std_scenario["cu_amount"] // 2 + 1): [
                    20,
                    21,
                    22,
                    23,
                    24,
                    25,
                    26,
                    27,
                    28,
                    29,
                    30,
                    31,
                    32,
                    33,
                    34,
                    35,
                ],
                (std_scenario["cu_amount"] // 2 + 2): [
                    20,
                    21,
                    22,
                    23,
                    24,
                    25,
                    26,
                    27,
                    28,
                    29,
                    30,
                    31,
                    32,
                    33,
                    34,
                    35,
                ],
            },
            "deal_start_epoch": 20,
            "deal_end_epoch": 40,
            "amount_of_cu_to_move_to_deal": std_scenario["cu_amount"] // 2,
        },  ## Move half of the CUs to deal and withdraw during deal
    ]

    run_multiple_scenarios(scenarios, "simulation_results_2.json")
