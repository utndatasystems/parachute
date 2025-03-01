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
AND (it1.id in ('6'))
AND (it2.id in ('4'))
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.role_id = rt.id
AND (mi1.info IN ('DTS','Datasat','Dolby Digital EX','Dolby Digital','Dolby SR','Dolby','Mono','SDDS','Stereo'))
AND (mi2.info IN ('Cantonese','Dutch','German','Greek','Hindi','Japanese','Mandarin','None','Russian','Serbian','Serbo-Croatian','Swedish'))
AND (kt.kind in ('episode','movie','tv movie','tv series','video game'))
AND (rt.role in ('composer','costume designer','miscellaneous crew'))
AND (n.gender IN ('f','m'))
AND (t.production_year <= 2015)
AND (t.production_year >= 1975)
AND (t.title in ('(#1.1174)','(#1.5356)','(#1.6051)','(#14.3)','(#3.79)','(#6.155)','(2002-10-10)','(2003-08-19)','(2004-11-29)','(2011-04-06)','Carte Blanche','Dangerous Women','Globos de Ouro 1998','In Darkness','Johnny Rockets','LL Cool J','No Meringue','Scavengers','Space Truckers','Stop the Presses','Suffer the Little Children','The Makeover','The Real Housewives Confess: A Watch What Happens Special','Turning Point'))
