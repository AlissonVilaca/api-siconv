--select sum(valor_global) from convenio

CREATE View total_convenios_por_ano_mes_data_assinatura
AS
select count(0) as total,
	sum(valor_global) as total_valor,
	cast(extract(year from data_assinatura) as varchar) || '-' || 
	cast(extract(month from data_assinatura) as varchar) || '-01' as data,
	cast(extract(year from data_assinatura) as integer) as ano, 
	cast(extract(month from data_assinatura) as integer) as mes 
from convenio 
group by ano, 
	 mes,
	 data 

order by ano asc, mes asc
;