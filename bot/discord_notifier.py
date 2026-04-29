from discord_webhook import DiscordWebhook, DiscordEmbed
import os
from loguru import logger

class DiscordNotifier:
    def __init__(self):
        self.signal_webhook = os.getenv('DISCORD_SIGNALS_WEBHOOK')
        self.high_conv_webhook = os.getenv('DISCORD_HIGH_CONV_WEBHOOK')
        self.logs_webhook = os.getenv('DISCORD_LOGS_WEBHOOK')

    def send_signal(self, embed_dict: dict, high_conviction: bool = False):
        url = self.high_conv_webhook if high_conviction else self.signal_webhook
        if not url: return
        webhook = DiscordWebhook(url=url)
        embed = DiscordEmbed.from_dict(embed_dict)
        webhook.add_embed(embed)
        try:
            response = webhook.execute()
            logger.info(f"Signal sent to Discord: {response.status_code}")
        except Exception as e:
            logger.error(f"Discord webhook error: {e}")

    def log_message(self, content: str):
        if self.logs_webhook:
            DiscordWebhook(url=self.logs_webhook, content=content).execute()
