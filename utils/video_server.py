"""Serve only registered lesson videos, with bounded-memory HTTP range support."""
import hashlib
import hmac
from pathlib import Path
import secrets

from starlette.responses import FileResponse, Response
from starlette.routing import Route
from streamlit import config

from .db import DatabaseManager

_SECRET = secrets.token_bytes(32)


def _token(lesson_id):
    return hmac.new(_SECRET, str(lesson_id).encode(), hashlib.sha256).hexdigest()


def video_url(lesson_id):
    base = config.get_option('server.baseUrlPath').strip('/')
    prefix = f'/{base}' if base else ''
    return f'{prefix}/videos/{lesson_id}/{_token(lesson_id)}'


def serve_video(request):
    lesson_id = request.path_params['lesson_id']
    if not hmac.compare_digest(request.path_params['token'], _token(lesson_id)):
        return Response(status_code=404)
    lesson = DatabaseManager().get_lesson_by_id(lesson_id)
    if not lesson:
        return Response(status_code=404)
    path = Path(lesson['filepath'])
    if not path.is_file() or path.suffix.lower() != '.mp4':
        return Response(status_code=404)
    return FileResponse(path, media_type='video/mp4',
                        headers={'Cache-Control': 'private, no-cache'})


def video_routes():
    base = config.get_option('server.baseUrlPath').strip('/')
    prefix = f'/{base}' if base else ''
    return [Route(prefix + '/videos/{lesson_id:int}/{token}', serve_video, methods=['GET', 'HEAD'])]
