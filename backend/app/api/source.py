"""Article preview and explicit prompt drafting; neither starts graph work."""
from flask import jsonify, request

from . import graph_bp
from ..services import url_source
from ..utils.locale import t


def _source_error(error):
    return jsonify(success=False, error=t(f'urlSource.{error.code}')), 502 if error.code in ('draftFailed', 'fetchFailed') else 400


@graph_bp.route('/source/preview', methods=['POST'])
def preview_source():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _source_error(url_source.SourceError('invalidUrl'))
    try:
        source = url_source.SourceStore.save(url_source.fetch_article(data.get('url')))
        return jsonify(success=True, data=source)
    except url_source.SourceError as error:
        return _source_error(error)


@graph_bp.route('/source/<source_id>/draft', methods=['POST'])
def draft_source(source_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _source_error(url_source.SourceError('invalidHorizon'))
    try:
        source = url_source.SourceStore.get(source_id)
        horizon = url_source.validate_horizon(data.get('horizon_hours', 72))
        return jsonify(success=True, data=url_source.draft_prompt(source, horizon))
    except url_source.SourceError as error:
        return _source_error(error)
