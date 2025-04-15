# app/services/validar_reclamo_chatgpt_usecase.py
from app.services.chatgpt_validar_reclamo_service import ChatGPTValidarReclamoService

class ValidarReclamoService:
    def __init__(self, chatgpt_validar_service: ChatGPTValidarReclamoService):
        self.chatgpt_validar_service = chatgpt_validar_service

    def ejecutar(self, descripcion, historial=""):
        return self.chatgpt_validar_service.validar_reclamo(descripcion, historial)