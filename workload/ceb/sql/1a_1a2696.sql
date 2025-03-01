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
AND (it2.id in ('17'))
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.role_id = rt.id
AND (mi1.info IN ('Bahamas','Bellevue Hospital - 550 First Avenue, Manhattan, New York City, New York, USA','Bray Studios, Down Place, Oakley Green, Berkshire, England, UK','Chicago, Illinois, USA','Colonial Street, Backlot, Universal Studios - 100 Universal City Plaza, Universal City, California, USA','England, UK','Hong Kong, China','Malibu, California, USA','Miami, Florida, USA','Spain','Sydney, New South Wales, Australia'))
AND (mi2.info IN ('Last show of the series.'))
AND (kt.kind in ('episode','movie','tv movie','tv series','video game','video movie'))
AND (rt.role in ('composer','writer'))
AND (n.gender IN ('m') OR n.gender IS NULL)
AND (t.production_year <= 1990)
AND (t.production_year >= 1950)
