from __future__ import annotations

from typing import Optional, List, Tuple, Union, TYPE_CHECKING

import discord
from discord import ButtonStyle, Interaction
from discord.utils import MISSING

from .converters import convert_emoji as _convert_emoji
from .ui import View


__all__ = ("ConfirmView",)


if TYPE_CHECKING:
    from bot import ModmailBot


def _validate_button_output(emoji: Optional[str], label: Optional[str]) -> bool:
    if emoji is None and label is None:
        return False
    return True


class ConfirmView(View):
    """
    Confirmation views. This can be used to add buttons on confirmation messages.

    Users can only select one of the accept and deny buttons on this view.
    After one of them is selected, the view will stop which means the bot will no longer listen to
    interactions on this view, and the buttons will be disabled.

    Example
    -------
    Changing the style and label:

        view = ConfirmView(ctx.bot, ctx.author)
        view.accept_button.style = discord.ButtonStyle.red
        view.accept_button.label = "Delete"
        view.deny_button.label = "Cancel"
        view.message = await ctx.send(
            "Are you sure you want to remove #very-important-channel?", view=view
        )
        await view.wait()
        if view.value:
            await ctx.send("Channel #very-important-channel deleted.")
        else:
            await ctx.send("Canceled.")

    Parameters
    -----------
    bot : ModmailBot
        The Modmail bot.
    user : Union[discord.Member, discord.User]
        The author that triggered this confirmation view.
    timeout : float
        Time before this view timed out. Defaults to `20` seconds.
    delete : bool
        Whether to delete the message after timeout or successful interaction
        has been made. For cleaner output, this defaults to `True`.
    """

    children: List[discord.ui.Button]

    def __init__(
        self,
        bot: ModmailBot,
        user: Union[discord.Member, discord.User],
        *,
        timeout: float = 20.0,
        delete: bool = True,
    ):
        self.bot: ModmailBot = bot
        self.user: Union[discord.Member, discord.User] = user
        self._delete_when_complete: bool = delete
        super().__init__(timeout=timeout)
        self._selected_button: discord.ui.Button = MISSING
        self.resolve_label_and_emoji()

    def resolve_label_and_emoji(self) -> None:
        _, accept_emoji, accept_style = self._retrieve_label_and_emoji(boolean=True)
        self.accept_button.label = None  # No label
        self.accept_button.emoji = accept_emoji
        self.accept_button.style = accept_style

        _, deny_emoji, deny_style = self._retrieve_label_and_emoji(boolean=False)
        self.deny_button.label = None  # No label
        self.deny_button.emoji = deny_emoji
        self.deny_button.style = deny_style

    def _retrieve_label_and_emoji(
        self,
        *,
        boolean: Optional[bool] = None,
        default_emoji_accept: Optional[str] = "✅",
        default_emoji_deny: Optional[str] = "❌",
        default_style_accept: ButtonStyle = ButtonStyle.green,
        default_style_deny: ButtonStyle = ButtonStyle.red,
    ) -> Tuple[Optional[str], Optional[Union[discord.PartialEmoji, discord.Emoji, str]], ButtonStyle]:
        if boolean is None:
            raise ValueError("boolean must be set to True or False.")

        label = None
        emoji = default_emoji_accept if boolean else default_emoji_deny
        style = default_style_accept if boolean else default_style_deny

        cog = self.bot.get_cog("Extended Utils")
        if cog is not None:
            attrs = ["emoji", "style"]
            config_emoji, config_style = (
                cog.config.get(f"confirm_button_{'accept' if boolean else 'deny'}_{attr}") for attr in attrs
            )

            emoji = config_emoji or emoji
            style = config_style or style

        return label, emoji, style

    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.message is MISSING:
            self.message = interaction.message
        if self.user.id == interaction.user.id:
            return True
        await interaction.response.send_message("These buttons cannot be controlled by you.", ephemeral=True)
        return False

    @discord.ui.button(emoji="✅", style=ButtonStyle.green)
    async def accept_button(self, interaction: Interaction, button: discord.ui.Button):
        """
        Ejecutado cuando el usuario presiona el botón de aceptación.
        """
        self.interaction = interaction
        self._selected_button = button
        self.value = True
        await self.conclude(interaction)

    @discord.ui.button(emoji="❌", style=ButtonStyle.red)
    async def deny_button(self, interaction: Interaction, button: discord.ui.Button):
        """
        Ejecutado cuando el usuario presiona el botón de denegación.
        """
        self.interaction = interaction
        self._selected_button = button
        self.value = False
        await self.conclude(interaction)

    async def conclude(self, interaction: Interaction) -> None:
        """
        Finalize and stop the view after interaction is made.

        Depends on the `.message` attribute, if it is ephemeral the message will be deleted.
        Otherwise it will be updated with all buttons disabled.
        """
        if self.message.flags.ephemeral or self._delete_when_complete:
            await interaction.response.defer()
            await interaction.delete_original_response()
        else:
            self.refresh()
            await interaction.response.edit_message(view=self)
        self.stop()

    def refresh(self) -> None:
        """
        Refresh the buttons on this view. If interaction has been made the buttons
        will be disabled.
        Unselected button will be greyed out.
        """
        for child in self.children:
            child.disabled = self.value is not None
            if self._selected_button and child != self._selected_button:
                child.style = discord.ButtonStyle.grey

    async def on_timeout(self) -> None:
        self.stop()
        if not self.message:
            return
        if self._delete_when_complete:
            await self.message.delete()
        else:
            self.refresh()
            await self.message.edit(view=self)
