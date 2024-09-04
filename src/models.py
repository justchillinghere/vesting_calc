from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Optional
import pydantic


class VestingParameters(BaseModel):
    vesting_period_count: int = Field(default=2, ge=1)
    vesting_period_duration: int = Field(default=6, ge=1)
    reward_per_epoch: int = Field(default=1, gt=0)


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
    cc_fail_epoch: Optional[int] = Field(default=None, ge=1)
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
    flt_price: float = Field(default=1.0, gt=0)

    @field_validator("deal_end_epoch")
    @classmethod
    def end_after_start(cls, v: int, info: pydantic.ValidationInfo) -> int:
        if "deal_start_epoch" in info.data:
            start = info.data["deal_start_epoch"]
            if start == 0 and v != 0:
                raise ValueError(
                    "If deal_start_epoch is 0, deal_end_epoch must also be 0"
                )
            if start != 0 and v <= start:
                raise ValueError(
                    "deal_end_epoch must be greater than deal_start_epoch when deal_start_epoch is not 0"
                )
        return v

    @field_validator("amount_of_cu_to_move_to_deal")
    @classmethod
    def validate_cu_amount(cls, v: int, info: pydantic.ValidationInfo) -> int:
        if "deal_start_epoch" in info.data and info.data["deal_start_epoch"] == 0:
            if v != 0:
                raise ValueError(
                    "amount_of_cu_to_move_to_deal must be 0 when there's no deal (deal_start_epoch is 0)"
                )
        return v


class CCParameters(BaseModel):
    vesting_params: VestingParameters = Field(default_factory=VestingParameters)
    creation_params: CCCreationParameters = Field(default_factory=CCCreationParameters)
    failing_params: CCFailingParams = Field(default_factory=CCFailingParams)
    deal_params: CCDealParameters = Field(default_factory=CCDealParameters)
    current_epoch: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_all(self) -> "CCParameters":
        if (
            self.deal_params.amount_of_cu_to_move_to_deal
            > self.creation_params.cu_amount
        ):
            raise ValueError(
                "amount_of_cu_to_move_to_deal cannot exceed total cu_amount"
            )

        deal_start = self.deal_params.deal_start_epoch
        deal_end = self.deal_params.deal_end_epoch
        cu_in_deal = self.deal_params.amount_of_cu_to_move_to_deal

        for cu, epochs in self.failing_params.slashed_epochs.items():
            if cu <= cu_in_deal:
                for epoch in epochs:
                    if deal_start <= epoch <= deal_end:
                        raise ValueError(
                            f"CU {cu} cannot be slashed in epoch {epoch} while in a deal"
                        )

        if self.failing_params.cc_fail_epoch is not None:
            if self.failing_params.cc_fail_epoch > self.creation_params.cc_end_epoch:
                raise ValueError("cc_fail_epoch cannot be after cc_end_epoch")
            if self.failing_params.cc_fail_epoch < self.creation_params.cc_start_epoch:
                raise ValueError("cc_fail_epoch cannot be before cc_start_epoch")

        return self
