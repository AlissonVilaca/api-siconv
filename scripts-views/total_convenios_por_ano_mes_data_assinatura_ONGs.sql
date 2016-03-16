CREATE View total_convenios_por_ano_mes_data_assinatura_ONGs
AS
select count(0) as total,
	sum(valor_global) as total_valor,
	cast(extract(year from data_assinatura) as varchar) || '-' || 
	cast(extract(month from data_assinatura) as varchar) || '-01' as data,
	cast(extract(year from data_assinatura) as integer) as ano, 
	cast(extract(month from data_assinatura) as integer) as mes 
from convenio conv
JOIN proponente prop on prop.id = conv.id_proponente

WHERE prop.id_natureza_juridica = 34
group by ano, 
	 mes,
	 data 

order by ano asc, mes asc