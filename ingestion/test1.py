SELECT t.c1
FROM table-name t
where c1 IS NOT NULL
group by t.c1
having count(t.c1) <= 1