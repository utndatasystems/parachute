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
AND (n.name_pcode_nf in ('C6261','D52','F6316','G5456','J5132','J5216','M5252','M5456','S3152'))
AND (ci.note in ('(voice)','(writer)') OR ci.note IS NULL)
AND (rt.role in ('actor','director','writer'))
AND (it1.id in ('32'))
