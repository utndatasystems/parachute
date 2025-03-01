SELECT COUNT(*) FROM title as t,
kind_type as kt,
info_type as it1,
movie_info as mi1,
movie_info as mi2,
info_type as it2,
cast_info as ci,
role_type as rt,
name as n
WHERE
t.id = ci.movie_id
AND t.id = mi1.movie_id
AND t.id = mi2.movie_id
AND mi1.movie_id = mi2.movie_id
AND mi1.info_type_id = it1.id
AND mi2.info_type_id = it2.id
AND (it1.id in ('1'))
AND (it2.id in ('5'))
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.role_id = rt.id
AND (mi1.info IN ('127','130','136','79','81','90','93','94','Argentina:60','USA:60'))
AND (mi2.info IN ('Australia:MA','Australia:PG','Canada:13+','Canada:G','France:-16','Iceland:16','Sweden:15','Sweden:Btl','UK:PG','UK:U','UK:X','USA:PG'))
AND (kt.kind in ('episode','movie','tv movie','tv series','video game','video movie'))
AND (rt.role in ('actor','actress','composer','guest','miscellaneous crew'))
AND (n.gender IN ('f') OR n.gender IS NULL)
AND (t.production_year <= 1990)
AND (t.production_year >= 1950)
