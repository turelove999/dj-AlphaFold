# Copyright 2024 DeepMind Technologies Limited
#
# AlphaFold 3 source code is licensed under CC BY-NC-SA 4.0. To view a copy of
# this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/
#
# To request access to the AlphaFold 3 model parameters, follow the process set
# out at https://github.com/google-deepmind/alphafold3. You may only use these
# if received directly from Google. Use is subject to terms of use available at
# https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md

"""Genetic search config settings for data pipelines."""

import dataclasses
import datetime
from typing import Self
from alphafold3.constants import mmcif_names


def _validate_chain_poly_type(chain_poly_type: str) -> None:
  if chain_poly_type not in mmcif_names.STANDARD_POLYMER_CHAIN_TYPES:
    raise ValueError(
        'chain_poly_type must be one of'
        f' {mmcif_names.STANDARD_POLYMER_CHAIN_TYPES}: {chain_poly_type}'
    )


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class DatabaseConfig:
  """Configuration for a database."""

  name: str
  path: str


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class JackhmmerConfig:
  """Configuration for a jackhmmer run.

  Attributes:
      binary_path: Path to the binary of the msa tool.
      database_config: Database configuration.
      n_cpu: An integer with the number of CPUs to use.
      n_iter: An integer with the number of database search iterations.
      e_value: e-value for the database lookup.
      z_value: The Z-value representing the number of comparisons done (i.e
        correct database size) for E-value calculation.
      max_sequences: Max sequences to return in MSA.
  """

  binary_path: str
  database_config: DatabaseConfig
  n_cpu: int
  n_iter: int
  e_value: float
  z_value: float | int | None
  max_sequences: int


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class NhmmerConfig:
  """Configuration for a nhmmer run.

  Attributes:
      binary_path: Path to the binary of the msa tool.
      hmmalign_binary_path: Path to the hmmalign binary.
      hmmbuild_binary_path: Path to the hmmbuild binary.
      database_config: Database configuration.
      n_cpu: An integer with the number of CPUs to use.
      e_value: e-value for the database lookup.
      max_sequences: Max sequences to return in MSA.
      alphabet: The alphabet when building a profile with hmmbuild.
  """

  binary_path: str
  hmmalign_binary_path: str
  hmmbuild_binary_path: str
  database_config: DatabaseConfig
  n_cpu: int
  e_value: float
  max_sequences: int
  alphabet: str | None


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class RunConfig:
  """Configuration for an MSA run.

  Attributes:
    config: MSA tool config.
    chain_poly_type: The chain type for which the tools will be run.
    crop_size: The maximum number of sequences to keep in the MSA. If None, all
      sequences are kept. Note that the query is included in the MSA, so it
      doesn't make sense to set this to less than 2.
  """

  config: JackhmmerConfig | NhmmerConfig
  chain_poly_type: str
  crop_size: int | None

  def __post_init__(self):
    if self.crop_size is not None and self.crop_size < 2:
      raise ValueError(f'crop_size must be None or >= 2: {self.crop_size}')

    _validate_chain_poly_type(self.chain_poly_type)


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class HmmsearchConfig:
  """Configuration for a hmmsearch."""

  hmmsearch_binary_path: str
  hmmbuild_binary_path: str

  e_value: float
  inc_e: float
  dom_e: float
  incdom_e: float
  alphabet: str = 'amino'
  filter_f1: float | None = None
  filter_f2: float | None = None
  filter_f3: float | None = None
  filter_max: bool = False


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class TemplateToolConfig:
  """Configuration for a template tool."""

  database_path: str
  chain_poly_type: str
  hmmsearch_config: HmmsearchConfig
  max_a3m_query_sequences: int | None = 300

  def __post_init__(self):
    _validate_chain_poly_type(self.chain_poly_type)


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class TemplateFilterConfig:
  """Configuration for a template filter."""

  max_subsequence_ratio: float | None
  min_align_ratio: float | None
  min_hit_length: int | None
  deduplicate_sequences: bool
  max_hits: int | None
  max_template_date: datetime.date

  @classmethod
  def no_op_filter(cls) -> Self:
    """Returns a config for filter that keeps everything."""
    return cls(
        max_subsequence_ratio=None,
        min_align_ratio=None,
        min_hit_length=None,
        deduplicate_sequences=False,
        max_hits=None,
        max_template_date=datetime.date(3000, 1, 1),  # Very far in the future.
    )


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class TemplatesConfig:
  """Configuration for the template search pipeline."""

  template_tool_config: TemplateToolConfig
  filter_config: TemplateFilterConfig
