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
AND (it1.id in ('5'))
AND (it2.id in ('7'))
AND t.kind_id = kt.id
AND ci.person_id = n.id
AND ci.role_id = rt.id
AND (mi1.info in ('Canada:PG','Canada:R','Germany:12','Norway:15','Singapore:NC-16','South Korea:12','Sweden:Btl'))
AND (mi2.info in ('PCS:Super 35','PFM:35 mm','RAT:2.35 : 1'))
AND (kt.kind in ('episode','movie','video movie'))
AND (rt.role in ('actress'))
AND (n.gender in ('f'))
AND (t.production_year <= 2015)
AND (t.production_year >= 1975)
AND (k.keyword IN ('baseball-cap','blessing-from-priest','brutalism','bucket-of-blood','dave-mirra','gay-subtext','headlamp','pleading-with-god','reference-to-bachir-gemayel','skopje-macedonia'))
