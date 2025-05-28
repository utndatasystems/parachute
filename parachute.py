import os
import csv
import utils
import num_histogram, str_histogram, like_histogram

UNCOMPUTED_MARKER = 0
from num_histogram import NULL_REPRESENTATION

class Parachute:
  # NOTE: If `like_tables` is None, then we don't restrict which tables should support LIKE.
  def __init__(self, data_dir, transitivity, adaptivity, pbw=None, catalog_path=None, con=None, support_like=True, like_tables=None, new_catalog=False, verbose=False):
    assert (pbw is not None) or (catalog_path is not None), 'We require that at least `pbw` or `catalog_path` are not None!'
    # TODO: In the future, maybe consider another parameter.
    # But we need this fixed one, so that we can uniquelly assign the data catalog somehow.
    self.con = con
    self.data_dir = data_dir
    # NOTE: This will be set in sniff.
    self.workload_name = ''
    self.support_like = support_like
    self.like_tables = like_tables
    self.schema = utils.read_json(os.path.join(self.data_dir, 'schema.json'))
    self.analysis = utils.read_json(os.path.join(self.data_dir, 'data-analysis.json'))
    self.verbose = verbose

    if new_catalog:
      assert pbw is not None, 'We need the parachute bit-width.'
      assert catalog_path is None, 'Note: You are not allowed to set `catalog_path`!'
      self.catalog = {}
      self.pbw = pbw
      self.transitivity = transitivity
      self.adaptivity = adaptivity
    else:
      assert catalog_path is not None
      assert pbw is None, 'Note: You are not allowed to set `pbw`!'
      assert catalog_path.endswith('.json')
      self.catalog_path = catalog_path

      print(f'catalog_path={catalog_path}')

      self.catalog = utils.read_json(self.catalog_path)
      assert '__init__' in self.catalog
      self.workload_name = self.catalog['__init__']['name']
      self.pbw = self.catalog['__init__']['pbw']
      self.transitivity = self.catalog['__init__']['transitivity']
      self.adaptivity = self.catalog['__init__']['adaptivity']

      # Check that we actually have the same catalog path in mind.
      assert self.catalog_path == self.get_catalog_path()

  @staticmethod
  def dummy_fields():
    return ['__init__', '__pre__']

  def mark_parachute(self, tn, col, status_type):
    assert status_type in ['is-computed']
    self.catalog[tn]['parachutes'][col][status_type] = 1

  def add_helper_to_catalog(self, pk_tn, pk_col):
    if pk_tn not in self.catalog:
      self.catalog[pk_tn] = {
        'parachutes' : {},
        'helpers' : {}
      }

    # Don't simply overwrite the value!
    if not pk_col in self.catalog[pk_tn]['helpers']:
      self.catalog[pk_tn]['helpers'][pk_col] = {
        'is-computed' : 0,
      }

  def add_parachute_to_catalog(self, data_type, is_nullable, tn, induced_col_info, histogram):
    if tn not in self.catalog:
      self.catalog[tn] = {
        'parachutes' : {},
        'helpers' : {}
      }

    def convert_hist_to_type(py_type, histogram):
      # Is the first bin with NULL only? Then store it as is and just convert the rest.
      if histogram[0] == NULL_REPRESENTATION:
        assert len(histogram) > 1
        return [None] + list(map(lambda elem: py_type(elem), histogram[1:]))

      # No NULLs in the first bin? Plain cast to `int`.
      return list(map(lambda elem: py_type(elem), histogram))  

    # Store as integers.
    # TODO: What about `float` types, like `numeric`?
    if data_type == 'integer':
      histogram = convert_hist_to_type(int, histogram)

    self.catalog[tn]['parachutes'][f"{induced_col_info['pk-tn']}.{induced_col_info['pk-col']}"] = {
      'tag' : f"{induced_col_info['pk-tn']}_{induced_col_info['pk-col']}",
      'is-computed' : 0,
      'type' : data_type,
      'is-nullable' : is_nullable,
      'requires' : induced_col_info['requires'],
      'info' : {
        'fk': induced_col_info['fk'],
        'pk': induced_col_info['pk'],
      },
      'crutch' : histogram
    }

  def read_induced_cols_from_schema(self, tn):
    def propagate(curr_tn, tab=0):
      tab_str = '\t' * tab
      if self.verbose:
        print(f'{tab_str} [propagate] curr_tn={curr_tn}')

      all_pk_cols = []
      for fk in self.schema[curr_tn]['fks']:
        elem = self.schema[curr_tn]['fks'][fk]
        pk_tn = elem['table']

        # Keep columns that are not keys.
        pk_cols = list(filter(lambda it: not utils.is_a_key(self.schema, pk_tn, it), self.schema[pk_tn]['columns']))

        # Remap.
        pk_cols = list(map(lambda it: {
          'fk' : fk,
          'pk-tn' : pk_tn,
          'pk' : elem['pk'],
          'pk-col' : it,
          # NOTE: Assumes a DAG structure.
          'requires': list(),
        }, pk_cols))

        # Propagate.
        if self.transitivity:
          other_pk_cols = propagate(pk_tn, tab = tab+1)

          # TODO: Use `map` or sth.
          # Add the current table as a requirement for the build-process.
          for it in other_pk_cols:
            it['requires'].append({
              'recursion-depth' : tab,
              'pk-tn' : pk_tn,
              'pk' : elem['pk'],
              'fk' : fk
            })
          all_pk_cols.extend(other_pk_cols)

        # TODO: Maybe check for duplicates?
        all_pk_cols.extend(pk_cols)
  
      if self.verbose:
        print(f'{tab_str} [propagate] FINISH {curr_tn}')
      return all_pk_cols

    # And propagate.
    collected_cols = propagate(tn)
    return collected_cols

  def collect_existing_aux_cols(self, tn, prefix='parachute_'):
    existing_columns = self.con.sql(f'PRAGMA table_info({tn});').df()['name'].values

    cols = []
    for col in existing_columns:
      if col.startswith(prefix):
        cols.append(col)
    return cols

  def sniff_parachute_cols(self, tn, workload_summary=None, uniqueness_threshold=2):
    # if tn not in ['movie_companies', 'cast_info', 'movie_info', 'movie_keyword']:
      # assert 0
    if tn == 'complete_cast':
      # Hack: Really hard to support two FKs.
      return

    collected_induced_cols = self.read_induced_cols_from_schema(tn)

    print(f'\nSniffing {tn}..')

    # print(collected_induced_cols)

    if workload_summary is not None:
      assert '__init__' in workload_summary
      if self.workload_name:
        assert self.workload_name == workload_summary['__init__']['name']
      self.workload_name = workload_summary['__init__']['name']

    for induced_col_info in collected_induced_cols:
      pk_tn = induced_col_info['pk-tn']
      col_name = induced_col_info['pk-col']
      col_schema_info = utils.get_col_info(self.schema, pk_tn, col_name)
      col_stats = utils.get_col_stats(self.analysis, pk_tn, col_name)

      # Check the workload (if any).
      if workload_summary is not None:
        # Is it inside?
        if not (pk_tn in workload_summary and col_name in workload_summary[pk_tn]):
          continue

        if self.verbose:
          print(f'Decide: pk_tn={pk_tn}, col_name={col_name}')

        # Check if we actually saw this column with the current, sniffed table.
        assert 'seen-with' in workload_summary[pk_tn][col_name]
        if tn not in workload_summary[pk_tn][col_name]['seen-with']:
          continue

        # Check if the number of distinct predicates is above the uniqueness threshold.            
        if len(workload_summary[pk_tn][col_name]['__templates__']) < uniqueness_threshold:
          continue

      print(f'{pk_tn}.{col_name} ++++> ENTER')

      if self.verbose:
        print(f'\n----\n[{pk_tn}] col_name={col_name}')

      # TODO: What to do with such columns?
      if 'only-null' in col_stats and col_stats['only-null']:
        continue

      # TODO: Why do we need to build the histograms?
      # Int?
      if col_schema_info['type'] == 'integer':
        histogram = num_histogram.build_adaptive_histogram(self.con, pk_tn, col_name, col_stats, self.pbw, self.catalog)
        if histogram is None:
          continue

        # Transform the boundaries into integers.
        # TODO: There is some repetitive work done here (since we sample multiple times for the same attribute).
        self.add_parachute_to_catalog(col_schema_info['type'], not col_schema_info['not-null'], tn, induced_col_info, histogram)
      elif col_schema_info['type'] == 'char':
        if col_stats['#distinct'] <= 255:
          histogram = str_histogram.build_str_histogram(col_name, col_stats, self.pbw)
          if histogram is None:
            continue
          self.add_parachute_to_catalog(col_schema_info['type'], not col_schema_info['not-null'], tn, induced_col_info, histogram)
        else:
          # Is this even possible?
          assert 0
      elif col_schema_info['type'] == 'varchar':
        if col_stats['#distinct'] <= 255:
          if not self.adaptivity:
            histogram = str_histogram.build_str_histogram(col_name, col_stats, self.pbw)
            if histogram is None:
              continue
          else:
            histogram = str_histogram.build_adaptive_str_histogram(self.con, tn, induced_col_info, col_stats, self.pbw)
            if histogram is None:
              continue
            
          self.add_parachute_to_catalog(col_schema_info['type'], not col_schema_info['not-null'], tn, induced_col_info, histogram)
        else:
          # This case is mainly for `LIKE` predicates.
          # TODO: What about `IN (...)` predicates? For now, we don't support them.
          # TODO: What about `BETWEEN` predicates, e.g., name_pcode_cf BETWEEN 'A' AND 'F'?

          # NOTE: Currently, we only introduce LIKE histograms for strings of unbounded lengths.
          if self.support_like:
            if self.like_tables is None or tn in self.like_tables:
              # NOTE: Doesn't make sense to optimize for this.
              if col_schema_info['length'] is None:
                histogram = like_histogram.build_like_histogram(col_name, col_stats, self.pbw)
                if histogram is None:
                  continue
                self.add_parachute_to_catalog(col_schema_info['type'], not col_schema_info['not-null'], tn, induced_col_info, histogram)          
        # else:
        #   # We now have two options.
        #   # If the column is like a primary key, use the ID as an int.
        #   # This necessitates a rewrite in the optimizer.
        #   id_stats = utils.get_
        #   if col_stats['#distinct'] == col_stats['#']

    self.persist()

  def reset(self, tn):
    terms = []
    for parachute_col in self.collect_existing_aux_cols(tn, prefix='parachute_'):
      terms.append(f'alter table {tn} drop {parachute_col};')
    for helper_col in self.collect_existing_aux_cols(tn, prefix='helper_'):
      terms.append(f'alter table {tn} drop {helper_col};')

    tmp = '\n'.join(terms)
    sql_stmt = tmp

    print(sql_stmt)
    if sql_stmt:
      self.con.sql(sql_stmt)

  def declare_parachute_cols(self, tn):
    # assert tn in ['movie_companies', 'cast_info', 'movie_info', 'movie_keyword']
    print(f'\nDeclare parachutes for {tn}..')

    if tn not in self.catalog:
      print(f'Table {tn} is not in the catalog!')
      return

    existing_parachute_col_names = self.collect_existing_aux_cols(tn, prefix='parachute_')

    # Just init the columns.
    terms = []
    for induced_col in self.catalog[tn]['parachutes']:
      # Check if already declared.
      # if self.catalog[tn]['parachutes'][induced_col]['is-declared']:
        # continue

      # Split the induced col to take `pk_tn` and `pk_col`.
      pk_tn, pk_col = induced_col.split('.')

      # Define the parachute column name.
      parachute_col_name = f"parachute_{self.catalog[tn]['parachutes'][induced_col]['tag']}"

      # assert parachute_col_name not in existing_parachute_col_names, "Maybe do a reset."

      # NOTE: Don't put this after the following `if`.
      terms.append(f'ALTER TABLE {tn} DROP  COLUMN IF EXISTS {parachute_col_name};')      
      terms.append(f'ALTER table {tn} ADD   COLUMN           {parachute_col_name} INTEGER DEFAULT {UNCOMPUTED_MARKER};')
      terms.append(f'ALTER TABLE {tn} ALTER COLUMN           {parachute_col_name} SET NOT NULL;')

      # Add the helper column, if needed.
      # TODO: Maybe all might need a helper.
      if self.catalog[tn]['parachutes'][induced_col]['type'] == 'varchar':
        if self.catalog[tn]['parachutes'][induced_col]['crutch']['type'] == 'like':
          # Add a parachute helper on the PK table.
          # Is it already computed?
          if pk_tn in self.catalog and pk_col in self.catalog[pk_tn]['helpers']:
            # NOTE: I mean, if it's already in, it should not be 0!!!
            # TODO: Re-enable this one.
            # assert self.catalog[pk_tn]['helpers'][pk_col]['is-computed']
            if self.catalog[pk_tn]['helpers'][pk_col]['is-computed']:
              # We skip this part, since the helper has already been added.
              # NOTE: This only happens if a previous table has added it!
              continue
          
          # Otherwise, consider it.
          self.add_helper_to_catalog(pk_tn, pk_col)
          parachute_helper_col_name = f"helper_{self.catalog[tn]['parachutes'][induced_col]['tag']}"

          # Declare.
          terms.append(f'ALTER TABLE {pk_tn} DROP  COLUMN IF EXISTS {parachute_helper_col_name};')
          terms.append(f'ALTER TABLE {pk_tn} ADD   COLUMN           {parachute_helper_col_name} INTEGER DEFAULT {UNCOMPUTED_MARKER};')
          terms.append(f'ALTER TABLE {pk_tn} ALTER COLUMN           {parachute_helper_col_name} SET NOT NULL;')

    # Create the SQL statement.
    tmp = '\n'.join(terms)
    sql_stmt = tmp

    print(sql_stmt)
    if sql_stmt:
      self.con.sql(sql_stmt)

  def compute_parachute_cols(self, tn):
    # assert tn in ['movie_companies', 'cast_info', 'movie_info', 'movie_keyword']
    # assert tn in self.catalog

    if tn not in self.catalog:
      print(f'Table {tn} is not in the catalog!')
      return
    
    # Ensure that we have parachutes for this table.
    assert 'parachutes' in self.catalog[tn]

    update_stmts = dict()
    for induced_col in self.catalog[tn]['parachutes']:
      # TODO: Adapt it to reflect the later change we will do to -1.
      # TODO: Maybe we can switch to use the catalog.

      # Already computed?
      # NOTE: This is only a light-weight check since we don't want to touch the db file.
      if self.catalog[tn]['parachutes'][induced_col]['is-computed']:
        continue

      # Define the parachute tag.
      parachute_tag = self.catalog[tn]['parachutes'][induced_col]['tag']

      # already_computed = self.con.sql(f'select count(*) from {tn} where {parachute_col_name} <> {UNCOMPUTED_MARKER};').fetchall()
      # if already_computed[0][0]:
      #   print(f'[{tn}] Column {parachute_col_name} is already computed.')
      #   continue

      # Check that it is already declared.
      # assert parachute_col_name.split('.')[1] in existing_parachute_col_names

      data_type = self.catalog[tn]['parachutes'][induced_col]['type']
      needs_helper = False
      if data_type == 'integer':
        histogram = num_histogram.NumHistogramWrapper(self.catalog[tn]['parachutes'][induced_col])
      elif data_type == 'char':
        assert 'type' in self.catalog[tn]['parachutes'][induced_col]['crutch']
        crutch_type = self.catalog[tn]['parachutes'][induced_col]['crutch']['type']
        assert crutch_type == 'lw'
        histogram = str_histogram.StrHistogramWrapper(self.catalog[tn]['parachutes'][induced_col])
      elif data_type == 'varchar':
        assert 'type' in self.catalog[tn]['parachutes'][induced_col]['crutch']
        crutch_type = self.catalog[tn]['parachutes'][induced_col]['crutch']['type']
        if crutch_type == 'lw':
          histogram = str_histogram.StrHistogramWrapper(self.catalog[tn]['parachutes'][induced_col])
        elif crutch_type == 'like':
          # assert 0
          needs_helper = True
          histogram = like_histogram.LikeHistogramWrapper(self.catalog[tn]['parachutes'][induced_col], self.con)
        else:
          assert 0
      else:
        assert 0

      # Take the PK-table and PK-column.
      pk_tn, pk_col = induced_col.split('.')

      # Take the original info.
      adaptive_info = self.catalog[tn]['parachutes'][induced_col]['info']
      assert 'pk-tn' not in adaptive_info
      adaptive_info['pk-tn'] = pk_tn

      # Mark for now as a non-transitive parachute.
      is_a_transitive_parachute = False

      # Do we have requirements?
      if self.catalog[tn]['parachutes'][induced_col]['requires']:
        # Then take the one with recursion depth 0.
        flag = False
        for out_info in self.catalog[tn]['parachutes'][induced_col]['requires']:
          if out_info['recursion-depth'] == 0:
            # Make sure we enter here only once.
            assert not flag
            flag = True
            adaptive_info = out_info
            assert 'pk-tn' in adaptive_info

            # Mark it as transitive.
            is_a_transitive_parachute = True
        assert flag, 'Sth went wrong.'

      # Hack.
      if is_a_transitive_parachute:
        # Switch the PK-table.
        pk_tn = adaptive_info['pk-tn']

        # We probably also don't need a helper. So disable it.
        needs_helper = False

      # Not already there?
      if pk_tn not in update_stmts:
        # NOTE: This invariant should be preserved.
        assert 'pk-tn' in adaptive_info
        assert adaptive_info['pk-tn'] == pk_tn
        update_stmts[pk_tn] = {
          'info' : adaptive_info,
          'parachutes' : [],
          'helpers' : [],
        }

      # NOTE: This doesn't hold anymore! Only if `info` is not special.
      # assert update_stmts[pk_tn]['info'] == self.catalog[tn]['parachutes'][induced_col]['info']

      # TODO: Maybe we should do the same for all, right?
      # TODO: The helpers should not have any requirement, right?
      if needs_helper:
        assert pk_col in self.catalog[pk_tn]['helpers']

        # Not yet computed?
        if not self.catalog[pk_tn]['helpers'][pk_col]['is-computed']:
          update_stmts[pk_tn]['helpers'].append({
            'col' : f'helper_{parachute_tag}',
            'def': f'helper_{parachute_tag} = {histogram.to_sql(induced_col, use_alias=False)}',
          })

          # Now mark it as computed.
          assert pk_tn in self.catalog

          # TODO: This only works if we indeed computed it.
          self.catalog[pk_tn]['helpers'][pk_col]['is-computed'] = 1

        # And define the parachute.
        assert not is_a_transitive_parachute
        update_stmts[pk_tn]['parachutes'].append(
          f'parachute_{parachute_tag} = {pk_tn}.helper_{parachute_tag}'
        )
      else:
        # Define the parachutes without helpers.
        if not is_a_transitive_parachute:
          update_stmts[pk_tn]['parachutes'].append(
            f'parachute_{parachute_tag} = {histogram.to_sql(induced_col)}'
          )
        else:
          # Transitive parachute.
          # NOTE: There is not need to access the histogram!

          # First check that it's already computed.
          assert self.catalog[pk_tn]['parachutes'][induced_col]['is-computed'], 'Sth went wrong in the transitive computation.'
          update_stmts[pk_tn]['parachutes'].append(
            f'parachute_{parachute_tag} = {pk_tn}.parachute_{parachute_tag}'
          )
      
      # Also mark the parachute columns as computed.
      # NOTE: This is still correct!
      self.mark_parachute(tn, induced_col, 'is-computed')
     
    # Stop early.
    if not update_stmts:
      return

    # TODO: We then need to sum with the other tables. Like update `+=`!
    for pk_tn in update_stmts:
      print(f'\nProcessing {pk_tn}')

      # First run the helpers.
      helpers = ',\n'.join(list(map(lambda elem: elem['def'], update_stmts[pk_tn]['helpers'])))
      if helpers:
        print(f'[{tn}] Compute helpers..')
        helpers_sql = f"""
          UPDATE {pk_tn}
          SET {helpers}
        """
        print(helpers_sql)
        self.con.sql(helpers_sql)

      # Then the actual parachutes.
      updates = ',\n'.join(update_stmts[pk_tn]['parachutes'])
      if updates:
        print(f'[{tn}] Compute parachutes..')
        parachutes_sql = f"""
          UPDATE {tn}
          SET {updates}
          FROM {pk_tn}
          WHERE {pk_tn}.{update_stmts[pk_tn]['info']['pk']} = {tn}.{update_stmts[pk_tn]['info']['fk']};
        """
        print(parachutes_sql)
        self.con.sql(parachutes_sql)

      # TODO: Drop later, since we might need them for other tables as well.
      # TODO: Maybe at the end.
      # Now drop the helpers.
      # drops = ',\n'.join(list(map(lambda elem: f'DROP COLUMN {elem['col']}', update_stmts[pk_tn]['helpers'])))
      # drop_sql = f'ALTER TABLE {pk_tn} {drops}'
      # if drops:
      #   print(drop_sql)
      #   self.con.sql(drop_sql)

    # Persist the catalog.
    self.persist()

  def drop_table_helper_columns(self, tn):
    if tn in Parachute.dummy_fields():
      return
    
    # No helpers? Then skip.
    if 'helpers' not in self.catalog[tn]:
      return

    # Take the helper columns.
    drops = []
    for cn in self.catalog[tn]['helpers']:
      assert self.catalog[tn]['helpers'][cn]['is-computed']
      helper_tag = f'helper_{tn}_{cn}'
      drops.append(f'DROP COLUMN {helper_tag}')
    drops = ',\n'.join(drops)

    if drops:
      drop_sql = f'ALTER TABLE {tn} {drops}'
      print(drop_sql)
      self.con.sql(drop_sql)

  def drop_db_helper_columns(self):
    for tn in self.catalog:
      print(f'[drop_db_helper_columns] tn={tn}')
      self.drop_table_helper_columns(tn)

  def compute_col_parachute_stats(self, tn, cn):
    parachute_tag = self.catalog[tn]['parachutes'][cn]['tag']
    parachute_cn = f'parachute_{parachute_tag}'

    query = f"""
      select {parachute_cn}, count(*) as counter
      from {tn}
      group by {parachute_cn}
      having count(*) > 0
      order by {parachute_cn};
    """

    print(query)

    dict_view = self.con.sql(query).df().to_dict()

    print(f'[compute_col_parachute_stats] tn={tn}, cn={parachute_cn}')
    # print(dic)

    # dict_view = ret.to_dict()

    print(dict_view)

    array_view = []
    for idx in dict_view[parachute_cn]:
      key = dict_view[parachute_cn][idx]
      array_view.append((key, dict_view['counter'][idx]))

    print(array_view)

    self.catalog[tn]['parachutes'][cn]['stats'] = array_view

  def compute_table_parachute_stats(self, tn):
    if tn in Parachute.dummy_fields():
      return
    assert 'parachutes' in self.catalog[tn]
    for cn in self.catalog[tn]['parachutes']:
      print(f'[compute_table_parachute_stats] cn={cn}')
      self.compute_col_parachute_stats(tn, cn)
    self.persist()

  def flush_db_parachute_stats(self):
    for tn in self.catalog:
      # if tn != 'movie_info_idx':
        # continue
      print(f'[compute_db_parachute_stats] tn={tn}')
      self.compute_table_parachute_stats(tn)
    self.persist()

    # And flush to the corresponding file.
    with open(os.path.join(self.data_dir, f'{self.workload_name}_parachute-stats-{self.pbw}-{self.transitivity}-{self.adaptivity}.csv'), 'w') as f:
      writer = csv.writer(f)
      for tn in self.catalog:
        # Skip.
        if tn in Parachute.dummy_fields():
          continue
        print(f'[compute_db_parachute_stats] tn={tn}')
        for cn in self.catalog[tn]['parachutes']:
          for idx, elem in enumerate(self.catalog[tn]['parachutes'][cn]['stats']):
            writer.writerow([2**self.pbw, tn, 'parachute_' + self.catalog[tn]['parachutes'][cn]['tag'], elem[0], elem[1]])
      f.close()

  def compute_space(self):
    # There are two ways.
    ret = self.con.execute('pragma database_size').fetchdf()

    return ret
    # for tn in self.catalog:
    #   table_size = utils.get_table_size(self.con, tn)
    #   for col in self.catalog[tn]['parachutes']:
    #     assert self.catalog[tn]['parachutes'][col]['is-computed']


  def get_catalog_path(self):
    assert self.pbw is not None
    return os.path.join(self.data_dir, f'{self.workload_name}_data-catalog-{self.pbw}-{self.transitivity}-{self.adaptivity}.json')

  def persist(self):
    self.catalog['__init__'] = {
      'name': self.workload_name,
      'pbw' : self.pbw,
      'transitivity' : self.transitivity,
      'adaptivity' : self.adaptivity,
    }
    utils.write_json(self.get_catalog_path(), self.catalog)

  def drop(self):
    assert os.path.isfile(self.get_catalog_path())
    os.remove(self.get_catalog_path())

  # def add_parachute_otf(self, fk_tn, pk_tn, col_name, parachute_name):
  #   # Add a dummy parachute name (non-condensated).
  #   terms = []
  #   terms.append(f'ALTER TABLE {fk_tn} DROP  COLUMN IF EXISTS {parachute_name};')
  #   terms.append(f'ALTER TABLE {fk_tn} ADD   COLUMN           {parachute_name} INTEGER DEFAULT 0;')
  #   terms.append(f'ALTER TABLE {fk_tn} ALTER COLUMN           {parachute_name} SET NOT NULL;')
  #   self.con.sql('\n'.join(terms))

  #   update_sql = f"""
  #     UPDATE {fk_tn}
  #     SET {parachute_name} = COALESCE({pk_tn}.{col_name}, 0)
  #     FROM {pk_tn}
  #     WHERE {pk_tn}.id = {fk_tn}.movie_id;
  #   """
  #   self.con.sql(update_sql)
  #   pass

  # def drop_parachute_otf(self, fk_tn, parachute_name):
  #   drop_sql = f'ALTER TABLE {fk_tn} DROP  COLUMN IF EXISTS {parachute_name};'
  #   self.con.sql(drop_sql)
  #   pass