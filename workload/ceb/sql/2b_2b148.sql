SELECT COUNT(*) FROM title as t,
kind_type as kt,
info_type as it1,
movie_info as mi1,
movie_info as mi2,
info_type as it2,
cast_info as ci,
role_type as rt,
name as n,
movie_keyword as mk,
keyword as k
WHERE
t.id = ci.movie_id
AND t.id = mi1.movie_id
AND t.id = mi2.movie_id
AND t.id = mk.movie_id
AND k.id = mk.keyword_id
AND mi1.movie_id = mi2.movie_id
AND mi1.info_type_id = it1.id
AND mi2.info_type_id = it2.id
AND (it1.id in ('2'))
AND (it2.id in ('18'))
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.role_id = rt.id
AND (mi1.info in ('Color'))
AND (mi2.info in ('Minneapolis, Minnesota, USA','Stage 17, Warner Brothers Burbank Studios - 4000 Warner Boulevard, Burbank, California, USA'))
AND (kt.kind in ('episode','movie','video movie'))
AND (rt.role in ('composer'))
AND (n.gender IS NULL)
AND (t.production_year <= 2015)
AND (t.production_year >= 1975)
AND (k.keyword IN ('anal-sex','bare-breasts','based-on-play','dog','family-relationships','female-frontal-nudity','fight','flashback','homosexual','interview','jealousy','lesbian-sex','male-frontal-nudity','mother-daughter-relationship','murder','police'))
