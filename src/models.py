from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Optional
import pydantic


class NetworkParameters(BaseModel):
    epoch_duration: int = Field(default=600, ge=1)  # in seconds
    usd_collateral_per_unit: float = Field(default=1.0, gt=0)
    usd_target_revenue_per_epoch: float = Field(default=1000.0, gt=0)
    # min_cc_duration: int = Field(default=1, ge=1)  # in epochs
    flt_usd_price: float = Field(default=1.0, gt=0)  # in USD
    min_reward_pool: float = Field(default=0.0, ge=0)  # in USD
    max_reward_pool: float = Field(default=0.0, ge=0)  # in USD
    max_fail_ratio: int = Field(default=4, ge=0)


class VestingParameters(BaseModel):
    vesting_period_count: int = Field(default=2, ge=1)
    vesting_period_duration: int = Field(default=6, ge=1)
    # reward_per_epoch: int = Field(default=1, gt=0)


class CCCreationParameters(BaseModel):
    cu_amount: int = Field(default=32, ge=1)
    cc_start_epoch: int = Field(default=1, ge=1)
    cc_end_epoch: int = Field(default=30, ge=1)
    staking_rate: int = Field(default=50, ge=0, le=100)

    @field_validator("cc_end_epoch")
    @classmethod
    def end_after_start(cls, v: int, info: pydantic.ValidationInfo) -> int:
        if "cc_start_epoch" in info.data and v <= info.data["cc_start_epoch"]:
            raise ValueError("cc_end_epoch must be greater than cc_start_epoch")
        return v


class CCFailingParams(BaseModel):
    cc_fail_epoch: int = Field(default=0, ge=0)
    slashed_epochs: Dict[int, List[int]] = Field(default_factory=dict)

    @field_validator("slashed_epochs")
    @classmethod
    def validate_slashed_epochs(cls, v: Dict[int, List[int]]) -> Dict[int, List[int]]:
        for cu, epochs in v.items():
            if not all(isinstance(epoch, int) and epoch >= 1 for epoch in epochs):
                raise ValueError(
                    f"All slashed epochs for CU {cu} must be positive integers"
                )
        return v


class CCDealParameters(BaseModel):
    deal_start_epoch: int = Field(default=0, ge=0)
    deal_end_epoch: int = Field(default=0, ge=0)
    amount_of_cu_to_move_to_deal: int = Field(default=0, ge=0)
    price_per_cu_in_offer_usd: float = Field(default=1.0, gt=0)

    @field_validator("deal_end_epoch")
    @classmethod
    def end_after_start(cls, v: int, info: pydantic.ValidationInfo) -> int:
        if "deal_start_epoch" in info.data:
            start = info.data["deal_start_epoch"]
            if start != 0 and v <= start:
                raise ValueError(
                    "deal_end_epoch must be greater than deal_start_epoch when deal_start_epoch is not 0"
                )
        return v

    @field_validator("amount_of_cu_to_move_to_deal")
    @classmethod
    def validate_cu_amount(cls, v: int, info: pydantic.ValidationInfo) -> int:
        if v == 0:
            if "deal_start_epoch" in info.data and info.data["deal_start_epoch"] != 0:
                raise ValueError(
                    "amount_of_cu_to_move_to_deal can be 0 when there's no deal (deal_start_epoch is 0)"
                )
        return v


class TestScenarioParameters(BaseModel):
    network_params: NetworkParameters = Field(default_factory=NetworkParameters)
    vesting_params: VestingParameters = Field(default_factory=VestingParameters)
    creation_params: CCCreationParameters = Field(default_factory=CCCreationParameters)
    failing_params: CCFailingParams = Field(default_factory=CCFailingParams)
    deal_params: CCDealParameters = Field(default_factory=CCDealParameters)
    precision: int = Field(default=10**7, ge=0)
    current_epoch: int = Field(default=1, ge=1)
    withdrawal_epoch: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_all(cls, values):
        if (
            values.deal_params.amount_of_cu_to_move_to_deal
            > values.creation_params.cu_amount
        ):
            raise ValueError(
                "amount_of_cu_to_move_to_deal cannot exceed total cu_amount"
            )

        deal_start = values.deal_params.deal_start_epoch
        deal_end = values.deal_params.deal_end_epoch
        cu_in_deal = values.deal_params.amount_of_cu_to_move_to_deal

        for cu, epochs in values.failing_params.slashed_epochs.items():
            if cu <= cu_in_deal:
                for epoch in epochs:
                    if (deal_start <= epoch <= deal_end) and (
                        deal_start != 0 and deal_end != 0 and cu_in_deal != 0
                    ):
                        raise ValueError(
                            f"CU {cu} cannot be slashed in epoch {epoch} while in a deal"
                        )

        cls.fill_slashed_epochs(values)
        cls.update_reward_pools(values.network_params, values.creation_params.cu_amount)

        if values.failing_params.cc_fail_epoch != 0:
            if (
                values.failing_params.cc_fail_epoch
                > values.creation_params.cc_end_epoch
            ):
                raise ValueError("cc_fail_epoch cannot be after cc_end_epoch")
            if (
                values.failing_params.cc_fail_epoch
                < values.creation_params.cc_start_epoch
            ):
                raise ValueError("cc_fail_epoch cannot be before cc_start_epoch")

        if values.withdrawal_epoch:
            if values.withdrawal_epoch > values.current_epoch:
                raise ValueError("withdrawal_epoch cannot be after current_epoch")

        return values

    @classmethod
    def fill_slashed_epochs(cls, values):
        network_params = values.network_params
        creation_params = values.creation_params
        failing_params = values.failing_params

        max_fail_amount = int(network_params.max_fail_ratio * creation_params.cu_amount)
        cc_fail_epoch = failing_params.cc_fail_epoch
        slashed_epochs = failing_params.slashed_epochs
        total_cu_amount = creation_params.cu_amount

        if cc_fail_epoch != 0 and not slashed_epochs:
            cls._fill_slashed_epochs_for_failure(
                cc_fail_epoch, max_fail_amount, total_cu_amount, slashed_epochs
            )
            failing_params.slashed_epochs = slashed_epochs

        total_slashed = sum(len(epochs) for epochs in slashed_epochs.values())
        cls._validate_slashed_epochs(cc_fail_epoch, total_slashed, max_fail_amount)

    @classmethod
    def _fill_slashed_epochs_for_failure(
        cls, cc_fail_epoch, max_fail_amount, total_cu_amount, slashed_epochs
    ):
        epochs_to_slash = max_fail_amount // total_cu_amount
        remaining_slashes = max_fail_amount % total_cu_amount

        for cu in range(1, total_cu_amount + 1):
            slashed_epochs[cu] = list(
                range(cc_fail_epoch - epochs_to_slash + 1, cc_fail_epoch + 1)
            )
            if cu <= remaining_slashes:
                slashed_epochs[cu].insert(0, cc_fail_epoch - epochs_to_slash)

    @classmethod
    def _validate_slashed_epochs(cls, cc_fail_epoch, total_slashed, max_fail_amount):
        if cc_fail_epoch != 0:
            if total_slashed < max_fail_amount:
                raise ValueError(
                    f"Total slashed epochs ({total_slashed}) must be at least {max_fail_amount} when cc_fail_epoch is set"
                )
        else:
            if total_slashed > max_fail_amount:
                raise ValueError(
                    f"Total slashed epochs ({total_slashed}) is greater than max_fail_amount ({max_fail_amount}), but cc_fail_epoch is not set"
                )

    @classmethod
    def update_reward_pools(cls, network_params: NetworkParameters, cu_amount: int):
        if network_params.min_reward_pool == 0 and network_params.max_reward_pool == 0:
            if network_params.flt_usd_price == 0 or cu_amount == 0:
                raise ValueError(
                    "FLT USD price and CU amount must be greater than zero"
                )

            reward_pool_value = (
                network_params.usd_target_revenue_per_epoch
                / network_params.flt_usd_price
            ) * cu_amount

            network_params.min_reward_pool = reward_pool_value
            network_params.max_reward_pool = reward_pool_value
