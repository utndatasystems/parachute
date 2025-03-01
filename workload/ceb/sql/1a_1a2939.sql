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
AND (it1.id in ('7'))
AND (it2.id in ('4'))
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.role_id = rt.id
AND (mi1.info IN ('CAM:Panavision Camera and Lenses','LAB:Laser Pacific Media Corporation, Los Angeles (CA), USA','LAB:Technicolor, USA','OFM:8 mm','PCS:(anamorphic)','PCS:HDTV','PFM:35 mm','PFM:DVD-ROM','RAT:1.85 : 1'))
AND (mi2.info IN ('Arabic','Catalan','Chinese','Czech','English','Estonian','Filipino','German','Greek','Korean','Persian','Russian','Swiss German','Thai'))
AND (kt.kind in ('episode','movie','tv movie','tv series','video movie'))
AND (rt.role in ('composer','director','guest','production designer'))
AND (n.gender IN ('m') OR n.gender IS NULL)
AND (t.production_year <= 2015)
AND (t.production_year >= 1975)
