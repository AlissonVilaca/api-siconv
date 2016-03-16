# -*- coding:utf-8 -*-
from pyspatialite import dbapi2 as sqlite

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy import Column, Integer, Unicode, Float, Date
from geoalchemy import GeometryDDL, GeometryColumn, Point
from geoalchemy.spatialite import SQLiteComparator

engine = create_engine("sqlite:////home/herrmann/dev/gis/geonames/BR/geonames_br.sqlite", module=sqlite)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Feature(Base):
    """A GeoNames geogaphical feature.
    """
    __tablename__ = "feature"
    geonameid = Column(Integer, primary_key=True)
    name = Column(Unicode)
    asciiname = Column(Unicode)
    alternatenames = Column(Unicode)
    latitude = Column(Float)
    longitude = Column(Float)
    feature_class = Column("feature class", Unicode)
    feature_code = Column("feature code", Unicode)
    country_code = Column("country code", Unicode)
    cc2 = Column(Unicode)
    admin1_code = Column("admin1 code", Unicode)
    admin2_code = Column("admin2 code", Unicode)
    admin3_code = Column("admin3 code", Unicode)
    admin4_code = Column("admin4 code", Unicode)
    population = Column(Integer)
    elevation = Column(Integer)
    gtopo30 = Column(Integer)
    timezone = Column(Unicode)
    modification_date = Column("modification date", Date)
    uf = Column(Unicode(2))
    position = GeometryColumn(Point(2), comparator=SQLiteComparator)

GeometryDDL(Feature.__table__)
