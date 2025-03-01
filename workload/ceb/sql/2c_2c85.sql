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
AND (it1.id in ('2'))
AND (it2.id in ('5'))
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.role_id = rt.id
AND (mi1.info IN ('Black and White','Color'))
AND (mi2.info IN ('Argentina:Atp','Canada:G','Finland:(Banned)','France:U','Iceland:16','Singapore:PG','Spain:T','USA:G','USA:Not Rated','USA:R','USA:Unrated'))
AND (kt.kind in ('episode','movie','tv series','video game','video movie'))
AND (rt.role in ('composer','costume designer','director','guest','producer'))
AND (n.gender IN ('m'))
AND (t.production_year <= 1975)
AND (t.production_year >= 1925)
AND (t.title in ('(#1.57)','(#3.33)','(#3.8)','(#4.13)','(#4.34)','A Bell for Adano','Blackmail','Divide and Conquer','Home Sweet Home','Kitty','La chica del gato','Man of a Thousand Faces','Parnell','Second Sight','The Fighting Devil Dogs','The Ringer'))
