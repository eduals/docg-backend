"""
Email Service - Send emails using SMTP with Jinja2 templates
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# SMTP Configuration from environment
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL')
SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', 'Pipehub')

# Template configuration
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'email')

# Initialize Jinja2 environment
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)


class EmailService:
    """Service for sending emails using SMTP and Jinja2 templates"""

    @staticmethod
    def _send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{SMTP_FROM_EMAIL}"
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add plain text version
            if text_content:
                msg.attach(MIMEText(text_content, 'plain'))

            # Add HTML version
            msg.attach(MIMEText(html_content, 'html'))

            # Send email
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    @staticmethod
    def send_otp_email(
        to_email: str,
        otp_code: str,
        otp_type: str,
        expires_in: int = 10
    ) -> bool:
        """
        Send OTP verification email.

        Args:
            to_email: Recipient email address
            otp_code: The OTP code
            otp_type: Type of OTP (EMAIL_VERIFICATION or PASSWORD_RESET)
            expires_in: Minutes until expiration (default: 10)

        Returns:
            True if email sent successfully
        """
        # Determine display text based on type
        otp_type_display = {
            'EMAIL_VERIFICATION': 'verificação de email',
            'PASSWORD_RESET': 'recuperação de senha'
        }.get(otp_type, 'autenticação')

        subject = f"Seu código de {otp_type_display} - Pipehub"

        # Render template
        template = jinja_env.get_template('otp_verification.html')
        html_content = template.render(
            otp_code=otp_code,
            otp_type_display=otp_type_display,
            expires_in=expires_in,
            year=datetime.now().year
        )

        # Plain text version
        text_content = f"""
Olá,

Você solicitou um código de verificação para {otp_type_display}.

Seu código: {otp_code}

Este código expira em {expires_in} minutos.

Nunca compartilhe este código com ninguém.
Nossa equipe nunca solicitará este código por telefone ou email.

Se você não solicitou este código, ignore este email.

---
Pipehub © {datetime.now().year}
        """.strip()

        return EmailService._send_email(to_email, subject, html_content, text_content)

    @staticmethod
    def send_welcome_email(
        to_email: str,
        first_name: str,
        app_url: str = 'http://localhost:4200'
    ) -> bool:
        """
        Send welcome email to new user.

        Args:
            to_email: Recipient email address
            first_name: User's first name
            app_url: URL to access the application

        Returns:
            True if email sent successfully
        """
        subject = f"Bem-vindo ao Pipehub, {first_name}!"

        # Render template
        template = jinja_env.get_template('welcome.html')
        html_content = template.render(
            first_name=first_name,
            app_url=app_url,
            year=datetime.now().year
        )

        # Plain text version
        text_content = f"""
Olá {first_name},

Bem-vindo ao Pipehub!

Estamos muito felizes em ter você conosco! Sua conta foi criada com sucesso
e você já pode começar a automatizar seus workflows.

Acesse: {app_url}

O que você pode fazer:
- Criar workflows visuais de automação
- Integrar com centenas de aplicativos
- Gerar documentos automaticamente
- Enviar emails e notificações
- Sincronizar dados entre sistemas

Se você tiver alguma dúvida, entre em contato: contato@pipehub.co

Boas vindas à bordo!

---
Pipehub © {datetime.now().year}
        """.strip()

        return EmailService._send_email(to_email, subject, html_content, text_content)

    @staticmethod
    def send_password_reset_success_email(
        to_email: str
    ) -> bool:
        """
        Send password reset confirmation email.

        Args:
            to_email: Recipient email address

        Returns:
            True if email sent successfully
        """
        subject = "Sua senha foi alterada - Pipehub"

        # Render template
        template = jinja_env.get_template('password_reset_success.html')
        html_content = template.render(
            year=datetime.now().year
        )

        # Plain text version
        text_content = f"""
Olá,

Sua senha foi alterada com sucesso.

Agora você já pode fazer login com sua nova senha.

Se você não fez esta alteração, entre em contato imediatamente:
contato@pipehub.co

Dicas de segurança:
- Use uma senha única e forte
- Nunca compartilhe sua senha
- Ative a autenticação de dois fatores (2FA)

---
Pipehub © {datetime.now().year}
        """.strip()

        return EmailService._send_email(to_email, subject, html_content, text_content)


def send_otp_email(to_email: str, otp_code: str, otp_type: str, expires_in: int = 10) -> bool:
    """Convenience function to send OTP email"""
    return EmailService.send_otp_email(to_email, otp_code, otp_type, expires_in)


def send_welcome_email(to_email: str, first_name: str, app_url: str = 'http://localhost:4200') -> bool:
    """Convenience function to send welcome email"""
    return EmailService.send_welcome_email(to_email, first_name, app_url)


def send_password_reset_success_email(to_email: str) -> bool:
    """Convenience function to send password reset confirmation"""
    return EmailService.send_password_reset_success_email(to_email)
