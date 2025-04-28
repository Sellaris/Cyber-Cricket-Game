import os
import click
from app import create_app

@click.command()
@click.option('--host', default='127.0.0.1', help='主机地址')
@click.option('--port', default=5000, help='端口号')
@click.option('--env', default='development', help='运行环境 (development/production)')
def run(host, port, env):
    """运行Cyber Cricket AI对战系统"""
    os.environ['FLASK_ENV'] = env
    app = create_app(env)
    
    if env == 'production':
        from waitress import serve
        click.echo(f'正在以生产模式运行，地址: http://{host}:{port}')
        serve(app, host=host, port=port)
    else:
        click.echo(f'正在以开发模式运行，地址: http://{host}:{port}')
        app.run(host=host, port=port, debug=True)

if __name__ == '__main__':
    run()