"""
Email Service for sending notifications via SMTP
"""
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


class EmailService:
    """Service for sending emails via SMTP"""
    
    def __init__(
        self,
        host: str,
        port: int = 587,
        user: str = None,
        password: str = None,
        from_email: str = None,
        use_tls: bool = True
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ):
        """Send an email"""
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = to_email
        
        # Add plain text part
        text_part = MIMEText(body, "plain")
        message.attach(text_part)
        
        # Add HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, "html")
            message.attach(html_part)
        
        # Para Gmail puerto 587: usar STARTTLS (start_tls=True, use_tls=False)
        # Para puerto 465: usar SSL directo (use_tls=True, start_tls=False)
        if self.port == 465:
            # Puerto 465: SSL directo
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                use_tls=True
            )
        else:
            # Puerto 587: STARTTLS
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                start_tls=True
            )
    
    async def send_test_email(self, to_email: str):
        """Send a test email to verify SMTP configuration"""
        subject = "100toLoose - Test Email"
        body = """
        This is a test email from your 100toLoose Trading Bot.
        
        If you received this email, your SMTP configuration is working correctly!
        
        Happy trading!
        """
        html_body = """
        <html>
          <body>
            <h2>100toLoose - Test Email</h2>
            <p>This is a test email from your 100toLoose Trading Bot.</p>
            <p>If you received this email, your SMTP configuration is working correctly!</p>
            <p><strong>Happy trading!</strong></p>
          </body>
        </html>
        """
        await self.send_email(to_email, subject, body, html_body)
    
    async def send_trade_notification(
        self,
        to_email: str,
        trade_type: str,
        symbol: str,
        price: float,
        quantity: float,
        profit_loss: Optional[float] = None
    ):
        """Send a trade notification email"""
        subject = f"100toLoose - {trade_type.upper()} {symbol}"
        
        if profit_loss is not None:
            pnl_text = f"P&L: ${profit_loss:.2f}"
            pnl_color = "green" if profit_loss >= 0 else "red"
        else:
            pnl_text = "Trade opened"
            pnl_color = "blue"
        
        body = f"""
        Trade Notification
        
        Type: {trade_type.upper()}
        Symbol: {symbol}
        Price: ${price:.8f}
        Quantity: {quantity:.8f}
        {pnl_text}
        """
        
        html_body = f"""
        <html>
          <body>
            <h2>Trade Notification</h2>
            <p><strong>Type:</strong> {trade_type.upper()}</p>
            <p><strong>Symbol:</strong> {symbol}</p>
            <p><strong>Price:</strong> ${price:.8f}</p>
            <p><strong>Quantity:</strong> {quantity:.8f}</p>
            <p><strong style="color: {pnl_color};">{pnl_text}</strong></p>
          </body>
        </html>
        """
        
        await self.send_email(to_email, subject, body, html_body)
    
    async def send_trading_summary(
        self,
        to_email: str,
        period: str,  # "daily", "weekly", etc.
        trades: list,  # List of trade dicts with: symbol, type, entry_price, exit_price, profit_loss, status, opened_at, closed_at
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        total_profit_loss: float,
        current_balance: float
    ):
        """Send a trading summary email"""
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        subject = f"100toLoose - Trading Summary ({period.capitalize()})"
        
        # Build trades table
        trades_html = ""
        if trades:
            trades_html = "<table border='1' cellpadding='8' style='border-collapse: collapse; width: 100%;'>"
            trades_html += "<tr style='background-color: #1a1a2e;'><th>Symbol</th><th>Type</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Status</th></tr>"
            for trade in trades[-20:]:  # Show last 20 trades
                pnl_color = "green" if trade.get("profit_loss", 0) >= 0 else "red"
                entry_price = trade.get('entry_price', 0) or 0
                exit_price = trade.get('exit_price') or entry_price
                profit_loss = trade.get('profit_loss', 0) or 0
                
                trades_html += f"""
                <tr>
                    <td>{trade.get('symbol', 'N/A')}</td>
                    <td>{trade.get('type', 'N/A')}</td>
                    <td>${entry_price:,.2f}</td>
                    <td>${exit_price:,.2f}</td>
                    <td style='color: {pnl_color};'>${profit_loss:,.2f}</td>
                    <td>{trade.get('status', 'N/A')}</td>
                </tr>
                """
            trades_html += "</table>"
        else:
            trades_html = "<p>No trades executed during this period.</p>"
        
        body = f"""
        Trading Summary - {period.capitalize()}
        
        Total Trades: {total_trades}
        Winning Trades: {winning_trades}
        Losing Trades: {losing_trades}
        Win Rate: {win_rate:.2f}%
        Total P&L: ${total_profit_loss:,.2f}
        Current Balance: ${current_balance:,.2f}
        """
        
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background-color: #0f0f1e; color: #e0e0e0;">
            <div style="max-width: 800px; margin: 0 auto; padding: 20px; background-color: #1a1a2e; border-radius: 8px;">
              <h2 style="color: #00d4ff;">100toLoose - Trading Summary</h2>
              <p style="color: #888;">Period: {period.capitalize()}</p>
              
              <div style="margin: 20px 0;">
                <h3 style="color: #00d4ff;">Statistics</h3>
                <ul style="list-style: none; padding: 0;">
                  <li><strong>Total Trades:</strong> {total_trades}</li>
                  <li><strong>Winning Trades:</strong> <span style="color: green;">{winning_trades}</span></li>
                  <li><strong>Losing Trades:</strong> <span style="color: red;">{losing_trades}</span></li>
                  <li><strong>Win Rate:</strong> {win_rate:.2f}%</li>
                  <li><strong>Total P&L:</strong> <span style="color: {'green' if total_profit_loss >= 0 else 'red'};">
                    ${total_profit_loss:,.2f}
                  </span></li>
                  <li><strong>Current Balance:</strong> ${current_balance:,.2f}</li>
                </ul>
              </div>
              
              <div style="margin: 20px 0;">
                <h3 style="color: #00d4ff;">Recent Trades</h3>
                {trades_html}
              </div>
              
              <p style="color: #888; margin-top: 30px; font-size: 12px;">
                This is an automated summary from your 100toLoose Trading Bot.
              </p>
            </div>
          </body>
        </html>
        """
        
        await self.send_email(to_email, subject, body, html_body)

