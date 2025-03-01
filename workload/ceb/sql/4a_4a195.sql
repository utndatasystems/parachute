SELECT COUNT(*)
FROM
name as n,
aka_name as an,
info_type as it1,
person_info as pi1,
cast_info as ci,
role_type as rt
WHERE
n.id = ci.person_id
AND ci.person_id = pi1.person_id
AND it1.id = pi1.info_type_id
AND n.id = pi1.person_id
AND n.id = an.person_id
AND ci.person_id = an.person_id
AND an.person_id = pi1.person_id
AND rt.id = ci.role_id
AND (n.gender in ('m'))
AND (n.name_pcode_nf in ('A4263','B6132','E3634','E526','M265','P3621','W4542'))
AND (ci.note in ('(adr loop group) (uncredited)','(producer)','(uncredited)','(writer)') OR ci.note IS NULL)
AND (rt.role in ('actor','miscellaneous crew','producer','writer'))
AND (it1.id in ('32'))
