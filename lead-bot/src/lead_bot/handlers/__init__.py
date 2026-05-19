from aiogram import Router

from . import admin, menu, survey


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(menu.router)
    root.include_router(survey.router)
    root.include_router(admin.router)
    return root
