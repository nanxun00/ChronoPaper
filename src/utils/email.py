import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import logging

logger = logging.getLogger("ChronoPaper.email")

def send_email_captcha(to_email: str, captcha: str):
    """
    发送邮箱验证码
    """
    smtp_server = os.getenv("SMTP_SERVER", "smtp.qq.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_user, smtp_password]):
        logger.error("SMTP configuration missing in .env")
        return False

    subject = 'ChronoPaper 注册验证码'
    content = f'''
    <html>
        <body>
            <h3>欢迎注册 ChronoPaper！</h3>
            <p>您的验证码是：<b style="color: #409EFF; font-size: 24px;">{captcha}</b></p>
            <p>验证码有效期为 5 分钟。如果不是您本人操作，请忽略此邮件。</p>
            <hr/>
            <p style="font-size: 12px; color: #999;">此邮件为系统自动发送，请勿回复。</p>
        </body>
    </html>
    '''

    message = MIMEText(content, 'html', 'utf-8')
    # QQ 邮箱要求 From 必须与登录账号完全一致，且格式必须标准
    message['From'] = f"ChronoPaper <{smtp_user}>"
    message['To'] = to_email
    message['Subject'] = Header(subject, 'utf-8')

    try:
        # 尝试使用普通的 SMTP 连接 (端口 587) 并升级到 TLS
        # QQ 邮箱的 587 端口通常比 465 端口在某些网络下更易成功完成握手
        server = smtplib.SMTP(smtp_server, 587, timeout=15)
        server.starttls() 
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [to_email], message.as_string())
        server.quit()
        logger.info(f"Captcha email sent to {to_email} via STARTTLS (587)")
        return True
    except Exception as e:
        logger.warning(f"QQ SMTP 587 failed: {str(e)}, trying SSL 465...")
        try:
            # 备选方案：使用传统的 SSL (465 端口)
            server = smtplib.SMTP_SSL(smtp_server, 465, timeout=15)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [to_email], message.as_string())
            server.quit()
            logger.info(f"Captcha email sent to {to_email} via SSL (465)")
            return True
        except Exception as ssl_e:
            logger.error(f"All QQ SMTP methods failed. Last error: {str(ssl_e)}")
            return False
