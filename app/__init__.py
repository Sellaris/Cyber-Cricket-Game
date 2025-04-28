from flask import Flask
from flask_cors import CORS
from .config import config
import os

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    
    # 允许跨域请求
    CORS(app)
    
    # 加载配置
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # 确保数据文件存在
    data_file = os.path.join(app.root_path, '..', 'ai_data.json')
    prompt_file = os.path.join(app.root_path, '..', 'prompt.txt')
    
    if not os.path.exists(data_file):
        with open(data_file, 'w', encoding='utf-8') as f:
            f.write('[]')
    
    if not os.path.exists(prompt_file):
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write('')
    
    # 注册蓝图
    from .api import api_bp
    app.register_blueprint(api_bp)
    
    # 错误处理
    @app.errorhandler(404)
    def page_not_found(e):
        return {"error": "页面未找到"}, 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return {"error": "服务器内部错误"}, 500
        
    return app