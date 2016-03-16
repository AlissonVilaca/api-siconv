--drop View total_convenios_em_vigencia_por_mes
CREATE OR REPLACE View total_convenios_em_vigencia_por_mes
AS

Select count(0) as total,
	sum(valor_global) as valorTotal,
	cast(extract(year from meses.data) as varchar) || '-' || 
	cast(extract(month from meses.data) as varchar) || '-01' as data, 
	cast(extract(year from meses.data) as integer) as ano, 
	cast(extract(month from meses.data) as integer) as mes 

FROM convenio conv
JOIN (SELECT (date '2008-01-01') + (s.a * '1 month'::INTERVAL) AS data 
	FROM generate_series(0,cast((12 * extract(YEAR from (age(now(), (date '2008-01-01')))) ) + 
		  extract(MONTH from (age(now(), (date '2008-01-01')))) as integer),1) as s(a)) meses
on meses.data between conv.data_inicio_vigencia and conv.data_fim_vigencia

Group By meses.data, data

order by meses.data asc;

--SELECT drop_matview('total_convenios_em_vigencia_por_mes_mv')
SELECT create_matview('total_convenios_em_vigencia_por_mes_mv', 'total_convenios_em_vigencia_por_mes');