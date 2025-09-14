from quart import Quart, jsonify
from quart_cors import cors
import config
import os, json, logging
from src.methods.cron_job import cron_fetch_job, init_scheduler
from src.routes.receive_mails_routes import receive_mail_bp
from src.routes.sent_mails_routes import sent_mail_bp
from database.db_pool import clear_db_pool, get_db_pool
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

def create_app():
    app = Quart(__name__)
    # app = cors(app, allow_origin="*")  # Allow all origins
    app.asgi_app = ProxyHeadersMiddleware(app.asgi_app, trusted_hosts=["*"])

    app.register_blueprint(receive_mail_bp)
    app.register_blueprint(sent_mail_bp)
    
    @app.before_serving
    async def startup():
        await get_db_pool()
        init_scheduler()
        # await cron_fetch_job()

    @app.after_serving
    async def shutdown():
        await clear_db_pool()

    # Define the home route
    @app.route("/")
    def home():
        return jsonify({"message": "Flask is running"})

    return app


app = create_app()

# Run the app
if __name__ == "__main__":
    # app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG) 
    app.run(host=getattr(config, "HOST", "127.0.0.1"),
            port=getattr(config, "PORT", 8000),
            debug=getattr(config, "DEBUG", False))

