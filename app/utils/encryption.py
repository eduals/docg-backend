from cryptography.fernet import Fernet
from app.config import Config
import base64
import os
import hashlib

# Gerar chave de criptografia (em produção, usar variável de ambiente)
def get_encryption_key():
    """
    Obtém chave de criptografia Fernet válida.
    Fernet requer uma string base64 URL-safe de exatamente 32 bytes decodificados.
    Retorna string (não bytes) que será usada diretamente pelo Fernet.
    """
    key = os.getenv('ENCRYPTION_KEY')
    
    if key:
        # Se ENCRYPTION_KEY está definida, validar formato
        key = key.strip()  # Remover espaços em branco
        try:
            # Tentar decodificar para validar formato base64 URL-safe
            decoded = base64.urlsafe_b64decode(key)
            if len(decoded) == 32:
                # Chave válida, retornar como string
                return key
            else:
                # Chave no formato errado, gerar nova
                print(f"Warning: ENCRYPTION_KEY tem tamanho incorreto ({len(decoded)} bytes). Gerando nova chave.")
        except Exception as e:
            # Chave inválida, gerar nova
            print(f"Warning: ENCRYPTION_KEY inválida: {e}. Gerando nova chave.")
    
    # Em desenvolvimento ou se ENCRYPTION_KEY não está definida/válida,
    # usar chave derivada do SECRET_KEY
    # Fernet precisa de exatamente 32 bytes codificados em base64 URL-safe
    from hashlib import sha256
    secret_key_bytes = Config.SECRET_KEY.encode('utf-8')
    key_bytes = sha256(secret_key_bytes).digest()  # SHA256 sempre retorna 32 bytes
    key = base64.urlsafe_b64encode(key_bytes).decode('utf-8')
    
    return key

def encrypt_credentials(data: dict) -> str:
    """
    Criptografa credenciais (tokens, API keys, etc.).
    
    Args:
        data: Dicionário com credenciais
    
    Returns:
        String criptografada (base64)
    """
    import json
    key = get_encryption_key()
    f = Fernet(key)
    
    json_data = json.dumps(data)
    encrypted = f.encrypt(json_data.encode())
    
    return base64.b64encode(encrypted).decode()

def decrypt_credentials(encrypted_data: str) -> dict:
    """
    Descriptografa credenciais.
    
    Args:
        encrypted_data: String criptografada (base64)
    
    Returns:
        Dicionário com credenciais
    """
    import json
    key = get_encryption_key()
    f = Fernet(key)
    
    encrypted_bytes = base64.b64decode(encrypted_data.encode())
    decrypted = f.decrypt(encrypted_bytes)
    
    return json.loads(decrypted.decode())

