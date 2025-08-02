from quart import Quart, jsonify
from quart_cors import cors
import config
from src.routes.receive_mails_routes import receive_mail_bp
from database.db_pool import clear_db_pool, get_db_pool

def create_app():
    app = Quart(__name__)
    app = cors(app, allow_origin="*")  # Allow all origins
    app.register_blueprint(receive_mail_bp)

    @app.before_serving
    async def startup():
        await get_db_pool()

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
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
