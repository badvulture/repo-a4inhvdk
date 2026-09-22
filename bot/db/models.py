import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


class SubscriptionTier(str, enum.Enum):
    NONE = "none"
    A_PLUS = "a_plus"
    A_PLUS_PLUS = "a_plus_plus"
    PREMIUM = "premium"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str | None] = mapped_column(String(128))
    lang: Mapped[str] = mapped_column(String(4), default="ru")
    balance: Mapped[int] = mapped_column(Integer, default=5)
    viewed_count: Mapped[int] = mapped_column(Integer, default=0)
    viewed_today: Mapped[int] = mapped_column(Integer, default=0)
    viewed_today_date: Mapped[str | None] = mapped_column(String(10))
    subscription: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier), default=SubscriptionTier.NONE
    )
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    referrer_id: Mapped[int | None] = mapped_column(BigInteger)
    ref_code: Mapped[str | None] = mapped_column(String(16), index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    captcha_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    lang_chosen: Mapped[bool] = mapped_column(Boolean, default=False)
    mirror_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    free_view_used: Mapped[bool] = mapped_column(Boolean, default=False)
    is_partner: Mapped[bool] = mapped_column(Boolean, default=False)
    partner_code: Mapped[str | None] = mapped_column(String(16), index=True)
    partner_credited: Mapped[bool] = mapped_column(Boolean, default=False)
    partner_balance_rub: Mapped[float] = mapped_column(Float, default=0)
    partner_withdrawn_rub: Mapped[float] = mapped_column(Float, default=0)
    partner_pending_rub: Mapped[float] = mapped_column(Float, default=0)
    last_bot_id: Mapped[int | None] = mapped_column(BigInteger)
    # author profile
    author_price: Mapped[int] = mapped_column(Integer, default=10)
    author_photo: Mapped[str | None] = mapped_column(String(256))
    author_photo_path: Mapped[str | None] = mapped_column(String(512))
    author_description: Mapped[str | None] = mapped_column(Text)
    author_earned: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    videos: Mapped[list["Video"]] = relationship(back_populates="owner")

    @property
    def has_active_subscription(self) -> bool:
        if self.subscription == SubscriptionTier.NONE:
            return False
        if self.subscription == SubscriptionTier.PREMIUM:
            return True
        return bool(
            self.subscription_until
            and self.subscription_until.replace(tzinfo=None) > datetime.utcnow()
        )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    seq_no: Mapped[int] = mapped_column(Integer, default=1)  # per-user numbering
    file_id: Mapped[str] = mapped_column(String(256))  # original telegram file_id
    note_file_id: Mapped[str | None] = mapped_column(String(256))  # video_note file_id
    local_path: Mapped[str | None] = mapped_column(String(512))  # path on server
    duration: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    dislikes: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    in_pool: Mapped[bool] = mapped_column(Boolean, default=False)  # common pool, not tied to a profile
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="videos")


class VideoFileCache(Base):
    """file_ids are bot-specific: cache the note file_id per (video, bot)."""

    __tablename__ = "video_file_cache"
    __table_args__ = (UniqueConstraint("video_id", "bot_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger)
    note_file_id: Mapped[str | None] = mapped_column(String(256))
    file_id: Mapped[str | None] = mapped_column(String(256))


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("user_id", "video_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    value: Mapped[int] = mapped_column(Integer)  # 1 like, -1 dislike


class View(Base):
    __tablename__ = "views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # coins / subscription / profile
    description: Mapped[str] = mapped_column(String(256))
    amount_coins: Mapped[int] = mapped_column(Integer, default=0)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProfileAccess(Base):
    __tablename__ = "profile_access"
    __table_args__ = (UniqueConstraint("buyer_id", "author_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    method: Mapped[str] = mapped_column(String(32))  # cryptobot / stars / manual / test
    coins: Mapped[int] = mapped_column(Integer)
    amount_rub: Mapped[int] = mapped_column(Integer, default=0)
    external_id: Mapped[str | None] = mapped_column(String(128))
    screenshot_file_id: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/paid/rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    details: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Sponsor(Base):
    __tablename__ = "sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)  # channel id (-100...)
    title: Mapped[str] = mapped_column(String(128))
    invite_link: Mapped[str] = mapped_column(String(256))
    required: Mapped[bool] = mapped_column(Boolean, default=True)  # forced sub
    # required = forced sub, optional = reward sub, recommend = advertised while viewing
    kind: Mapped[str] = mapped_column(String(16), default="required")
    reward_coins: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SponsorReward(Base):
    __tablename__ = "sponsor_rewards"
    __table_args__ = (UniqueConstraint("user_id", "sponsor_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("sponsors.id"))


class SponsorHidden(Base):
    """Sponsors the user asked not to be recommended again. A deleted +
    re-added sponsor is a new sponsors row, so it is shown again."""

    __tablename__ = "sponsor_hidden"
    __table_args__ = (UniqueConstraint("user_id", "sponsor_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sponsor_id: Mapped[int] = mapped_column(
        ForeignKey("sponsors.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Mirror(Base):
    __tablename__ = "mirrors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token: Mapped[str] = mapped_column(String(128), unique=True)
    bot_username: Mapped[str | None] = mapped_column(String(64))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    sub_tier: Mapped[str | None] = mapped_column(String(16))  # a_plus/a_plus_plus/premium
    sub_days: Mapped[int] = mapped_column(Integer, default=0)  # 0 = forever
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PromoActivation(Base):
    __tablename__ = "promo_activations"
    __table_args__ = (UniqueConstraint("promo_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    promo_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
