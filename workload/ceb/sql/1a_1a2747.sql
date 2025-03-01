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
AND (it1.id in ('18'))
AND (it2.id in ('4'))
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.role_id = rt.id
AND (mi1.info IN ('Albuquerque, New Mexico, USA','Boston, Massachusetts, USA','China','Hamilton, Ontario, Canada','St. Louis, Missouri, USA','Sweden','Sydney, New South Wales, Australia'))
AND (mi2.info IN ('Croatian','Czech','Hindi','Japanese','Mandarin','Serbo-Croatian','Swiss German'))
AND (kt.kind in ('movie','tv movie','tv series','video game'))
AND (rt.role in ('composer'))
AND (n.gender IN ('f','m') OR n.gender IS NULL)
AND (t.production_year <= 2015)
AND (t.production_year >= 1975)
