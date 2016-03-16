#!/usr/bin/python
import wsdasiconv
from sqlalchemy import create_engine
#url = "postgresql+psycopg2://postgres:@10.209.54.50:23456/siconv_NOVO"
url = "postgresql+psycopg2://postgres:sltidgei@10.209.8.147:5432/siconv_teste2"
engine = create_engine(url, implicit_returning=False)
from sqlalchemy.orm import Session
session = Session(bind=engine)
from wsdasiconv.model import Base
metadata = Base.metadata
metadata.bind = engine
metadata.create_all()
session.close()
