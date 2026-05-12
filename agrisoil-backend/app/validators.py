"""
Validadores customizados e constraints para Pydantic
Garante entrada de dados robusta e segura
"""
from pydantic import field_validator, EmailStr, HttpUrl
from typing import Optional
import re


class ValidatorsMixin:
    """Mixin com validadores reutilizáveis para modelos Pydantic"""
    
    @field_validator('email', mode='before')
    @classmethod
    def validate_email(cls, v):
        """Valida e normaliza email"""
        if not v:
            return v
        
        v = v.lower().strip()
        
        # Regex básico para email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Email inválido')
        
        return v
    
    @field_validator('phone', mode='before')
    @classmethod
    def validate_phone(cls, v):
        """Valida e limpa número de telefone"""
        if not v:
            return v
        
        # Remove caracteres não numéricos
        v = re.sub(r'\D', '', v)
        
        # Valida tamanho (Brasil: 10-11 dígitos)
        if len(v) < 10 or len(v) > 11:
            raise ValueError('Telefone deve ter 10-11 dígitos')
        
        return v
    
    @field_validator('url', mode='before')
    @classmethod
    def validate_url(cls, v):
        """Valida URL"""
        if not v:
            return v
        
        url_pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
        if not re.match(url_pattern, v):
            raise ValueError('URL inválida')
        
        return v
    
    @field_validator('name', mode='before')
    @classmethod
    def validate_name(cls, v):
        """Valida nome (mínimo 2 caracteres)"""
        if not v:
            return v
        
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError('Nome deve ter pelo menos 2 caracteres')
        
        if len(v) > 255:
            raise ValueError('Nome não pode exceder 255 caracteres')
        
        return v
    
    @field_validator('username', mode='before')
    @classmethod
    def validate_username(cls, v):
        """Valida username (alphanumerico + underscore)"""
        if not v:
            return v
        
        v = v.lower().strip()
        
        if not re.match(r'^[a-z0-9_]{3,32}$', v):
            raise ValueError('Username deve ter 3-32 caracteres (letras, números, underscore)')
        
        return v
    
    @field_validator('password', mode='before')
    @classmethod
    def validate_password(cls, v):
        """Valida força da senha"""
        if not v:
            return v
        
        # Mínimo 8 caracteres
        if len(v) < 8:
            raise ValueError('Senha deve ter pelo menos 8 caracteres')
        
        # Máximo 128 caracteres
        if len(v) > 128:
            raise ValueError('Senha não pode exceder 128 caracteres')
        
        # Deve ter pelo menos 1 maiúscula, 1 minúscula, 1 número
        if not re.search(r'[A-Z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Senha deve conter pelo menos uma letra minúscula')
        
        if not re.search(r'\d', v):
            raise ValueError('Senha deve conter pelo menos um número')
        
        return v
    
    @field_validator('cpf', mode='before')
    @classmethod
    def validate_cpf(cls, v):
        """Valida CPF brasileiro"""
        if not v:
            return v
        
        # Remove caracteres não numéricos
        v = re.sub(r'\D', '', v)
        
        # Deve ter 11 dígitos
        if len(v) != 11:
            raise ValueError('CPF deve ter 11 dígitos')
        
        # Valida dígitos verificadores (básico)
        if v == v[0] * 11:
            raise ValueError('CPF inválido')
        
        return v
    
    @field_validator('cnpj', mode='before')
    @classmethod
    def validate_cnpj(cls, v):
        """Valida CNPJ brasileiro"""
        if not v:
            return v
        
        # Remove caracteres não numéricos
        v = re.sub(r'\D', '', v)
        
        # Deve ter 14 dígitos
        if len(v) != 14:
            raise ValueError('CNPJ deve ter 14 dígitos')
        
        # Valida dígitos repetidos (básico)
        if v == v[0] * 14:
            raise ValueError('CNPJ inválido')
        
        return v
    
    @field_validator('latitude', mode='before')
    @classmethod
    def validate_latitude(cls, v):
        """Valida latitude (-90 a 90)"""
        if v is None:
            return v
        
        try:
            v = float(v)
        except (ValueError, TypeError):
            raise ValueError('Latitude deve ser um número')
        
        if v < -90 or v > 90:
            raise ValueError('Latitude deve estar entre -90 e 90')
        
        return v
    
    @field_validator('longitude', mode='before')
    @classmethod
    def validate_longitude(cls, v):
        """Valida longitude (-180 a 180)"""
        if v is None:
            return v
        
        try:
            v = float(v)
        except (ValueError, TypeError):
            raise ValueError('Longitude deve ser um número')
        
        if v < -180 or v > 180:
            raise ValueError('Longitude deve estar entre -180 e 180')
        
        return v
