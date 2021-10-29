# Copyright 2021 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Full AlphaFold protein structure prediction script."""
import json
import os
import pathlib
import pickle
import random
import sys
import time
from typing import Dict

from absl import app
from absl import flags
from absl import logging
from alphafold.common import protein
from alphafold.common import residue_constants
from alphafold.data import pipeline
from alphafold.data import templates
from alphafold.model import data
from alphafold.model import config
from alphafold.model import model
from alphafold.relax import relax
import numpy as np
# Internal import (7716).

import configparser
from alphafold.common.hutils import getconf_chains

flags.DEFINE_list('fasta_paths', None, 'Paths to FASTA files, each containing '
                  'one sequence. Paths should be separated by commas. '
                  'All FASTA paths must have a unique basename as the '
                  'basename is used to name the output directories for '
                  'each prediction.')
flags.DEFINE_string('output_dir', None, 'Path to a directory that will '
                    'store the results.')
flags.DEFINE_list('model_names', None, 'Names of models to use.')
flags.DEFINE_string('data_dir', None, 'Path to directory of supporting data.')
flags.DEFINE_string('jackhmmer_binary_path', '/usr/bin/jackhmmer',
                    'Path to the JackHMMER executable.')
flags.DEFINE_string('hhblits_binary_path', '/usr/bin/hhblits',
                    'Path to the HHblits executable.')
flags.DEFINE_string('hhsearch_binary_path', '/usr/bin/hhsearch',
                    'Path to the HHsearch executable.')
flags.DEFINE_string('kalign_binary_path', '/usr/bin/kalign',
                    'Path to the Kalign executable.')
flags.DEFINE_string('uniref90_database_path', None, 'Path to the Uniref90 '
                    'database for use by JackHMMER.')
flags.DEFINE_string('mgnify_database_path', None, 'Path to the MGnify '
                    'database for use by JackHMMER.')
flags.DEFINE_string('bfd_database_path', None, 'Path to the BFD '
                    'database for use by HHblits.')
flags.DEFINE_string('small_bfd_database_path', None, 'Path to the small '
                    'version of BFD used with the "reduced_dbs" preset.')
flags.DEFINE_string('uniclust30_database_path', None, 'Path to the Uniclust30 '
                    'database for use by HHblits.')
flags.DEFINE_string('pdb70_database_path', None, 'Path to the PDB70 '
                    'database for use by HHsearch.')
flags.DEFINE_string('template_mmcif_dir', None, 'Path to a directory with '
                    'template mmCIF structures, each named <pdb_id>.cif')
flags.DEFINE_string('max_template_date', None, 'Maximum template release date '
                    'to consider. Important if folding historical test sets.')
flags.DEFINE_string('obsolete_pdbs_path', None, 'Path to file containing a '
                    'mapping from obsolete PDB IDs to the PDB IDs of their '
                    'replacements.')
flags.DEFINE_enum('preset', 'full_dbs',
                  ['reduced_dbs', 'full_dbs', 'casp14'],
                  'Choose preset model configuration - no ensembling and '
                  'smaller genetic database config (reduced_dbs), no '
                  'ensembling and full genetic database config  (full_dbs) or '
                  'full genetic database config and 8 model ensemblings '
                  '(casp14).')
flags.DEFINE_boolean('benchmark', False, 'Run multiple JAX model evaluations '
                     'to obtain a timing that excludes the compilation time, '
                     'which should be more indicative of the time required for '
                     'inferencing many proteins.')
flags.DEFINE_integer('random_seed', None, 'The random seed for the data '
                     'pipeline. By default, this is randomly generated. Note '
                     'that even if this is set, Alphafold may still not be '
                     'deterministic, because processes like GPU inference are '
                     'nondeterministic.')
flags.DEFINE_string("config_file", None, 'Configuration file with arguments '
                    'and parameters.')
FLAGS = flags.FLAGS

MAX_TEMPLATE_HITS = 20
RELAX_MAX_ITERATIONS = 0
RELAX_ENERGY_TOLERANCE = 2.39
RELAX_STIFFNESS = 10.0
RELAX_EXCLUDE_RESIDUES = []
RELAX_MAX_OUTER_ITERATIONS = 20


def _check_flag(flag_name: str, preset: str, should_be_set: bool):
  if should_be_set != bool(FLAGS[flag_name].value):
    verb = 'be' if should_be_set else 'not be'
    raise ValueError(f'{flag_name} must {verb} set for preset "{preset}"')


def predict_structure(
    fasta_path: str,
    fasta_name: str,
    output_dir_base: str,
    data_pipeline: pipeline.DataPipeline,
    model_runners: Dict[str, model.RunModel],
    amber_relaxer: relax.AmberRelaxation,
    benchmark: bool,
    random_seed: int,
    hconfig: configparser.ConfigParser = None):
  """Predicts structure using AlphaFold for the given sequence."""
  timings = {}
  output_dir = hconfig.get("paths", "output_dir", fallback=os.path.join(output_dir_base, fasta_name))
  if not os.path.exists(output_dir):
    os.makedirs(output_dir)
  msa_output_dir = os.path.join(output_dir, 'msas')
  if not os.path.exists(msa_output_dir):
    os.makedirs(msa_output_dir)

  running_get_features = hconfig.getboolean("steps", "get_features", fallback=True)

  if running_get_features:
    logging.info("*** hege: running get_features")
    # Get features.
    t_0 = time.time()
    feature_dict = data_pipeline.process(
        input_fasta_path=fasta_path,
        msa_output_dir=msa_output_dir,
        hconfig=hconfig)
    timings['features'] = time.time() - t_0

    # Write out features as a pickled dictionary.
    features_output_path = os.path.join(output_dir, 'features.pkl')
    with open(features_output_path, 'wb') as f:
      pickle.dump(feature_dict, f, protocol=4)
    timings_output_path = os.path.join(output_dir, 'timings-features.json')
    with open(timings_output_path, 'w') as f:
      f.write(json.dumps(timings, indent=4))

  # loading from previous one
  else:
    logging.info("*** hege: skipping running get_features, loading from prev run")
    features_output_path = os.path.join(output_dir, 'features.pkl')
    feature_dict = pickle.load(open(features_output_path, 'rb'))

  # Run the models.
  running_models = hconfig.getboolean("steps", "run_models", fallback=True)
  if running_models:
    logging.info("*** hege: running models")
    plddts = {}
    for model_name, model_runner in model_runners.items():
      logging.info('Running model %s', model_name)
      t_0 = time.time()
      processed_feature_dict = model_runner.process_features(
          feature_dict, random_seed=random_seed)
      timings[f'process_features_{model_name}'] = time.time() - t_0

      t_0 = time.time()
      prediction_result = model_runner.predict(processed_feature_dict)
      t_diff = time.time() - t_0
      timings[f'predict_and_compile_{model_name}'] = t_diff
      logging.info(
          'Total JAX model %s predict time (includes compilation time, see --benchmark): %.0f?',
          model_name, t_diff)

      if benchmark:
        t_0 = time.time()
        model_runner.predict(processed_feature_dict)
        timings[f'predict_benchmark_{model_name}'] = time.time() - t_0

      # Get mean pLDDT confidence metric.
      plddt = prediction_result['plddt']
      plddts[model_name] = np.mean(plddt)

      # Save the model outputs.
      result_output_path = os.path.join(output_dir, f'result_{model_name}.pkl')
      with open(result_output_path, 'wb') as f:
        pickle.dump(prediction_result, f, protocol=4)

      # Add the predicted LDDT in the b-factor column.
      # Note that higher predicted LDDT value means higher model confidence.
      plddt_b_factors = np.repeat(
          plddt[:, None], residue_constants.atom_type_num, axis=-1)
      unrelaxed_protein = protein.from_prediction(  # This is a Protein object
          features=processed_feature_dict,
          result=prediction_result,
          b_factors=plddt_b_factors)

      unrelaxed_pdb_path = os.path.join(output_dir, f'unrelaxed_{model_name}.pdb')
      with open(unrelaxed_pdb_path, 'w') as f:
        f.write(protein.to_pdb(unrelaxed_protein))
      # unrelaxed_pkl_path = os.path.join(output_dir, f'unrelaxed_protein_{model_name}.pkl')
      # with open(unrelaxed_pkl_path, 'wb') as f:
      #   pickle.dump(unrelaxed_protein, f)

    plddts_pkl_path = os.path.join(output_dir, 'ranking_debug.json')
    with open(plddts_pkl_path, 'w') as f:
      json.dump({'plddts': plddts}, f)

    timings_output_path = os.path.join(output_dir, 'timings-models.json')
    with open(timings_output_path, 'w') as f:
      f.write(json.dumps(timings, indent=4))

  else:
    logging.info("*** hege: skipping running models")
      
  # RUNNING RELAX
  running_relax = hconfig.getboolean("steps", "run_relax", fallback=True)
  if running_relax:
    logging.info("*** hege: running relax")

    plddts_path = os.path.join(output_dir, f'ranking_debug.json')
    plddts = json.load(open(plddts_path))['plddts']

    resiD = None
    if hconfig:
      chainD = getconf_chains(hconfig)
    
    ranked_order = []
    for idx, (model_name, _) in enumerate(
        sorted(plddts.items(), key=lambda x: x[1], reverse=True)):
      ranked_order.append(model_name)

    relax_models = hconfig.get("relax", "models", fallback="model_1,model_2,model_3,model_4,model_5")
    if relax_models == "top":
      relax_models == ranked_order[0]

    for model_name in relax_models.split(","):
      unrelaxed_pdb_path = os.path.join(output_dir, f'unrelaxed_{model_name}.pdb')
      # unrelaxed_protein = pickle.load(open(unrelaxed_pdb_path, 'rb'))
      unrelaxed_protein = protein.from_pdb_string(open(unrelaxed_pdb_path).read())
      
      # Relax the prediction.
      t_0 = time.time()
      relaxed_pdb_str, _, _ = amber_relaxer.process(prot=unrelaxed_protein, chainD=chainD)
      timings[f'relax_{model_name}'] = time.time() - t_0

      # Save the relaxed PDB.
      relaxed_output_path = os.path.join(output_dir, f'relaxed_{model_name}.pdb')
      with open(relaxed_output_path, 'w') as f:
        f.write(relaxed_pdb_str)

      idx = ranked_order.index(model_name)
      ranked_output_path = os.path.join(output_dir, f'ranked_{idx}.pdb')
      with open(ranked_output_path, 'w') as f:
        f.write(relaxed_pdb_str)

    ranking_output_path = os.path.join(output_dir, 'ranking_debug.json')
    with open(ranking_output_path, 'w') as f:
      f.write(json.dumps({'plddts': plddts, 'order': ranked_order}, indent=4))
      
  logging.info('Final timings for %s: %s', fasta_name, timings)
  timings_output_path = os.path.join(output_dir, 'timings.json')
  with open(timings_output_path, 'w') as f:
    f.write(json.dumps(timings, indent=4))


def main(argv):
  if len(argv) > 1:
    raise app.UsageError('Too many command-line arguments.')

  use_small_bfd = FLAGS.preset == 'reduced_dbs'
  _check_flag('small_bfd_database_path', FLAGS.preset,
              should_be_set=use_small_bfd)
  _check_flag('bfd_database_path', FLAGS.preset,
              should_be_set=not use_small_bfd)
  _check_flag('uniclust30_database_path', FLAGS.preset,
              should_be_set=not use_small_bfd)

  if FLAGS.preset in ('reduced_dbs', 'full_dbs'):
    num_ensemble = 1
  elif FLAGS.preset == 'casp14':
    num_ensemble = 8

  # hegelab
  hconfig = configparser.ConfigParser()
  if FLAGS.config_file:
    hconfig.read([fn for fn in FLAGS.config_file.split(",")])

  # Check for duplicate FASTA file names.
  fasta_names = [pathlib.Path(p).stem for p in FLAGS.fasta_paths]
  if len(fasta_names) != len(set(fasta_names)):
    raise ValueError('All FASTA paths must have a unique basename.')

  template_mmcif_dir = hconfig.get("paths", "template_mmcif_dir", fallback=FLAGS.template_mmcif_dir)
  obsolete_pdbs_path = hconfig.get("paths", "obsolete_pdbs_path", fallback=FLAGS.obsolete_pdbs_path)
  max_template_hits = hconfig.get("hhsearch_pdb70", "max_template_hits", fallback=MAX_TEMPLATE_HITS)
  max_template_date = hconfig.get("hhsearch_pdb70", "max_template_date", fallback=FLAGS.max_template_date)
  
  template_featurizer = templates.TemplateHitFeaturizer(
      mmcif_dir=template_mmcif_dir,
      max_template_date=max_template_date,
      max_hits=max_template_hits,
      kalign_binary_path=FLAGS.kalign_binary_path,
      release_dates_path=None,
      obsolete_pdbs_path=obsolete_pdbs_path)

  uniref90_database_path = hconfig.get("paths", "uniref90_database_path", fallback=FLAGS.uniref90_database_path)
  mgnify_database_path = hconfig.get("paths", "mgnify_database_path", fallback=FLAGS.mgnify_database_path)
  bfd_database_path = hconfig.get("paths", "bfd_database_path", fallback=FLAGS.bfd_database_path)
  uniclust30_database_path = hconfig.get("paths", "uniclust30_database_path", fallback=FLAGS.uniclust30_database_path)
  small_bfd_database_path = hconfig.get("paths", "small_bfd_database_path", fallback=FLAGS.small_bfd_database_path)
  pdb70_database_path = hconfig.get("paths", "pdb70_database_path", fallback=FLAGS.pdb70_database_path)
  
  data_pipeline = pipeline.DataPipeline(
      jackhmmer_binary_path=FLAGS.jackhmmer_binary_path,
      hhblits_binary_path=FLAGS.hhblits_binary_path,
      hhsearch_binary_path=FLAGS.hhsearch_binary_path,
      uniref90_database_path=uniref90_database_path,
      mgnify_database_path=mgnify_database_path,
      bfd_database_path=bfd_database_path,
      uniclust30_database_path=uniclust30_database_path,
      small_bfd_database_path=small_bfd_database_path,
      pdb70_database_path=pdb70_database_path,
      template_featurizer=template_featurizer,
      use_small_bfd=use_small_bfd)

  model_runners = {}
  for model_name in FLAGS.model_names:
    model_config = config.model_config(model_name)
    model_config.data.eval.num_ensemble = num_ensemble
    model_params = data.get_model_haiku_params(
        model_name=model_name, data_dir=FLAGS.data_dir)
    model_runner = model.RunModel(model_config, model_params)
    model_runners[model_name] = model_runner

  logging.info('Have %d models: %s', len(model_runners),
               list(model_runners.keys()))

  amber_relaxer = relax.AmberRelaxation(
      max_iterations=RELAX_MAX_ITERATIONS,
      tolerance=RELAX_ENERGY_TOLERANCE,
      stiffness=RELAX_STIFFNESS,
      exclude_residues=RELAX_EXCLUDE_RESIDUES,
      max_outer_iterations=RELAX_MAX_OUTER_ITERATIONS)

  random_seed = FLAGS.random_seed
  if random_seed is None:
    random_seed = random.randrange(sys.maxsize)
  logging.info('Using random seed %d for the data pipeline', random_seed)

  # Predict structure for each of the sequences.
  for fasta_path, fasta_name in zip(FLAGS.fasta_paths, fasta_names):
    predict_structure(
        fasta_path=fasta_path,
        fasta_name=fasta_name,
        output_dir_base=FLAGS.output_dir,
        data_pipeline=data_pipeline,
        model_runners=model_runners,
        amber_relaxer=amber_relaxer,
        benchmark=FLAGS.benchmark,
        random_seed=random_seed,
        hconfig=hconfig)


if __name__ == '__main__':
  flags.mark_flags_as_required([
      'fasta_paths',
      'output_dir',
      'model_names',
      'data_dir',
      'preset',
      'uniref90_database_path',
      'mgnify_database_path',
      'pdb70_database_path',
      'template_mmcif_dir',
      'max_template_date',
      'obsolete_pdbs_path',
  ])

  app.run(main)
