import sqlite3

db = sqlite3.connect("yrss2.db")
db.execute(
    """
ALTER TABLE "video" 
    ADD COLUMN "short" BOOLEAN DEFAULT FALSE;
"""
)
db.commit()
