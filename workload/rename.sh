for dir in */; do
  echo $dir
  for f in "$dir"*.sql; do
    mv "$f" "${dir%/}_$(basename "$f")"
  done
done
