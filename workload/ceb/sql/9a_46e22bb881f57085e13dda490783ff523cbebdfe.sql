SELECT mi1.info, pi.info, COUNT(*)
FROM title as t,
kind_type as kt,
movie_info as mi1,
info_type as it1,
cast_info as ci,
role_type as rt,
name as n,
info_type as it2,
person_info as pi
WHERE
t.id = ci.movie_id
AND t.id = mi1.movie_id
AND mi1.info_type_id = it1.id
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.movie_id = mi1.movie_id
AND ci.role_id = rt.id
AND n.id = pi.person_id
AND pi.info_type_id = it2.id
AND (it1.id IN ('90'))
AND (it2.id IN ('23'))
AND (mi1.info ILIKE '%%')
AND (pi.info ILIKE '%1966%')
AND (kt.kind IN ('movie','tv movie','tv series','video game','video movie'))
AND (rt.role IN ('actor','actress','cinematographer','guest','producer','production designer','writer'))
GROUP BY mi1.info, pi.info
