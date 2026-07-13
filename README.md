# SLCRP Main Bot (24/7)

## Deploy (Railway)
1. Create a new Railway project from this GitHub repository.
2. Add environment variables from .env.example in Railway Variables.
3. To run seed features on a separate bot token, also set `FAS_SEED_BOT_TOKEN`.
4. Deploy; Procfile runs the worker continuously.

## Local Run
pip install -r requirements.txt
python bot_fresh_standalone.py
