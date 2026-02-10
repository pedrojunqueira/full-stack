from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "textsummary" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "url" TEXT NOT NULL,
    "summary" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztll1vmzAUhv8K4qqVuqpl6Yd2x9JszdQkU8O2qlWFHHAIirGpbdpEVf77fAyEjxCUTZ"
    "PWTLuD97zG5zw2Pn41I+ZjIo4dvJDjJIoQX5ofjFeTogirh6bwkWGiOC6CIEg0IdovlVGU"
    "jBMhOfKkCk0REVhJPhYeD2MZMqpUmhACIvOUMaRBISU0fEqwK1mA5QxzFXh4VHJIfbzAIn"
    "+N5+40xMSvJB36MLfWXbmMtdan8pM2wmwT12MkiWhhjpdyxujaHVIJaoAp5khi+LzkCaQP"
    "2WXF5hWlmRaWNMXSGB9PUUJkqdwdGXiMAj+VjdAFBjDLO+u0c9G5fH/euVQWnclauVil5R"
    "W1pwM1gaFjrnQcSZQ6NMaCW8LJJjhY+mZymb2GTiVcR5eDamOXCwW8YsP8GXotaJzenQNJ"
    "R0I8ERCG3+3b7rV9ezCw7w51ZJlFbkbDz7mdqa2dbvth92b0UdMtaJZ+g12Jlob8FtVsv/"
    "3DUD2OoXwXyU2uVyoiwwg3s62OrOH1s6HH+cPb3MKmqsEfUbLM1rqNfn/QGzv24GtlCa5s"
    "pwcRq4I/Vw/OD6srsP6I8aPvXBvwatyPhj1NkAkZcD1j4XPuTcgJJZK5lL24yC8dg7mag1"
    "nBAT6dl44iECbIm78g7rsbEWaxbd7NUGRFdQVRFOhlAbiQZtbcbMxDb9bU9rJIa8dDhed/"
    "s9ujZveMuYCUNuB1Z4g30ysN2Zemp3b9wiWYBhI2uHV21sIsP56Vq3YO5Ce3lcaqRzL8Gr"
    "8AMbPvJ8DTk5MdACrXVoA6VutpjEpMGxral/FouKWZFUNqIL9RVeCDH3ryyCChkI9vE2sL"
    "Rai6/d5QvyLUuhF8AO4Nf7W9rH4CbCBCHw=="
)
