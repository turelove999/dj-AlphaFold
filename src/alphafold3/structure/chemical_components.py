# Copyright 2024 DeepMind Technologies Limited
#
# AlphaFold 3 source code is licensed under CC BY-NC-SA 4.0. To view a copy of
# this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/
#
# To request access to the AlphaFold 3 model parameters, follow the process set
# out at https://github.com/google-deepmind/alphafold3. You may only use these
# if received directly from Google. Use is subject to terms of use available at
# https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md

"""Utilities for manipulating chemical components data."""

from collections.abc import Iterable, Mapping, Sequence
import dataclasses
import functools
from typing import Self

from alphafold3.constants import chemical_components
from alphafold3.constants import residue_names
from alphafold3.structure import mmcif
import rdkit.Chem as rd_chem


@dataclasses.dataclass(frozen=True)
class ChemCompEntry:
  """Items of _chem_comp category.

  For the full list of items and their semantics see
  http://mmcif.rcsb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/chem_comp.html
  """

  type: str
  name: str = '?'
  pdbx_synonyms: str = '?'
  formula: str = '?'
  formula_weight: str = '?'
  mon_nstd_flag: str = '?'
  pdbx_smiles: str | None = None

  def __post_init__(self):
    for field, value in vars(self).items():
      if not value and value is not None:
        raise ValueError(f"{field} value can't be an empty string.")

  def extends(self, other: Self) -> bool:
    """Checks whether this ChemCompEntry extends another one."""
    for field, value in vars(self).items():
      other_value = getattr(other, field)
      if _value_is_missing(other_value):
        continue
      if value != other_value:
        return False
    return True

  @property
  def rdkit_mol(self) -> rd_chem.Mol:
    """Returns an RDKit Mol, created via RDKit from entry SMILES string."""
    if not self.pdbx_smiles:
      raise ValueError('Cannot construct RDKit Mol with empty pdbx_smiles')
    return rd_chem.MolFromSmiles(self.pdbx_smiles)


_REQUIRED_MMCIF_COLUMNS = ('_chem_comp.id', '_chem_comp.type')


class MissingChemicalComponentsDataError(Exception):
  """Raised when chemical components data is missing from an mmCIF."""


@dataclasses.dataclass(frozen=True)
class ChemicalComponentsData:
  """Extra information for chemical components occurring in mmCIF.

  Fields:
    chem_comp: A mapping from _chem_comp.id to associated items in the
      chem_comp category.
  """

  chem_comp: Mapping[str, ChemCompEntry]

  @classmethod
  def from_mmcif(
      cls, cif: mmcif.Mmcif, fix_mse: bool, fix_unknown_dna: bool
  ) -> Self:
    """Constructs an instance of ChemicalComponentsData from an Mmcif object."""
    for col in _REQUIRED_MMCIF_COLUMNS:
      if col not in cif:
        raise MissingChemicalComponentsDataError(col)

    id_ = cif['_chem_comp.id']  # Guaranteed to be present.
    type_ = cif['_chem_comp.type']  # Guaranteed to be present.
    name = cif.get('_chem_comp.name', ['?'] * len(id_))
    synonyms = cif.get('_chem_comp.pdbx_synonyms', ['?'] * len(id_))
    formula = cif.get('_chem_comp.formula', ['?'] * len(id_))
    weight = cif.get('_chem_comp.formula_weight', ['?'] * len(id_))
    mon_nstd_flag = cif.get('_chem_comp.mon_nstd_flag', ['?'] * len(id_))
    smiles = cif.get('_chem_comp.pdbx_smiles', ['?'] * len(id_))
    smiles = [None if s == '?' else s for s in smiles]

    chem_comp = {
        component_name: ChemCompEntry(*entry)
        for component_name, *entry in zip(
            id_, type_, name, synonyms, formula, weight, mon_nstd_flag, smiles
        )
    }

    if fix_mse and 'MSE' in chem_comp:
      if 'MET' not in chem_comp:
        chem_comp['MET'] = ChemCompEntry(
            type='L-PEPTIDE LINKING',
            name='METHIONINE',
            pdbx_synonyms='?',
            formula='C5 H11 N O2 S',
            formula_weight='149.211',
            mon_nstd_flag='y',
            pdbx_smiles=None,
        )

    if fix_unknown_dna and 'N' in chem_comp:
      # Do not delete 'N' as it may be needed for RNA in the system.
      if 'DN' not in chem_comp:
        chem_comp['DN'] = ChemCompEntry(
            type='DNA LINKING',
            name="UNKNOWN 2'-DEOXYNUCLEOTIDE",
            pdbx_synonyms='?',
            formula='C5 H11 O6 P',
            formula_weight='198.111',
            mon_nstd_flag='y',
            pdbx_smiles=None,
        )

    return ChemicalComponentsData(chem_comp)

  def to_mmcif_dict(self) -> Mapping[str, Sequence[str]]:
    """Returns chemical components data as a dict suitable for `mmcif.Mmcif`."""
    mmcif_dict = {}

    mmcif_fields = set()
    for entry in self.chem_comp.values():
      for field, value in vars(entry).items():
        if value:
          mmcif_fields.add(field)
    chem_comp_ids = []
    for component_id in sorted(self.chem_comp):
      entry = self.chem_comp[component_id]
      chem_comp_ids.append(component_id)
      for field in mmcif_fields:
        mmcif_dict.setdefault(f'_chem_comp.{field}', []).append(
            getattr(entry, field) or '?'
        )
    if chem_comp_ids:
      mmcif_dict['_chem_comp.id'] = chem_comp_ids
    return mmcif_dict


def _value_is_missing(value: str) -> bool:
  return not value or value in ('.', '?')


def get_data_for_ccd_components(
    ccd: chemical_components.Ccd,
    chemical_component_ids: Iterable[str],
    populate_pdbx_smiles: bool = False,
) -> ChemicalComponentsData:
  """Returns `ChemicalComponentsData` for chemical components known by PDB."""
  chem_comp = {}
  for chemical_component_id in chemical_component_ids:
    chem_data = chemical_components.component_name_to_info(
        ccd=ccd, res_name=chemical_component_id
    )
    if not chem_data:
      continue
    chem_comp[chemical_component_id] = ChemCompEntry(
        type=chem_data.type,
        name=chem_data.name,
        pdbx_synonyms=chem_data.pdbx_synonyms,
        formula=chem_data.formula,
        formula_weight=chem_data.formula_weight,
        mon_nstd_flag=chem_data.mon_nstd_flag,
        pdbx_smiles=(
            chem_data.pdbx_smiles or None if populate_pdbx_smiles else None
        ),
    )
  return ChemicalComponentsData(chem_comp=chem_comp)


def populate_missing_ccd_data(
    ccd: chemical_components.Ccd,
    chemical_components_data: ChemicalComponentsData,
    chemical_component_ids: Iterable[str] | None = None,
    populate_pdbx_smiles: bool = False,
) -> ChemicalComponentsData:
  """Populates missing data for the chemical components from CCD.

  Args:
    ccd: The chemical components database.
    chemical_components_data: ChemicalComponentsData to populate missing values
      for. This function doesn't modify the object, extended version is provided
      as a return value.
    chemical_component_ids: chemical components to populate missing values for.
      If not specified, the function will consider all chemical components which
      are already present in `chemical_components_data`.
    populate_pdbx_smiles: whether to populate `pdbx_smiles` field using SMILES
      descriptors from _pdbx_chem_comp_descriptor CCD table. If CCD provides
      multiple SMILES strings, any of them could be used.

  Returns:
    New instance of ChemicalComponentsData without missing values for CCD
    entries.
  """
  if chemical_component_ids is None:
    chemical_component_ids = chemical_components_data.chem_comp.keys()

  ccd_data = get_data_for_ccd_components(
      ccd, chemical_component_ids, populate_pdbx_smiles
  )
  chem_comp = dict(chemical_components_data.chem_comp)
  for component_id, ccd_entry in ccd_data.chem_comp.items():
    if component_id not in chem_comp:
      chem_comp[component_id] = ccd_entry
    else:
      already_specified_fields = {
          field: value
          for field, value in vars(chem_comp[component_id]).items()
          if not _value_is_missing(value)
      }
      chem_comp[component_id] = ChemCompEntry(
          **{**vars(ccd_entry), **already_specified_fields}
      )
  return ChemicalComponentsData(chem_comp=chem_comp)


def get_all_atoms_in_entry(
    ccd: chemical_components.Ccd, res_name: str
) -> Mapping[str, Sequence[str]]:
  """Get all possible atoms and bonds for this residue in a standard order.

  Args:
    ccd: The chemical components dictionary.
    res_name: Full CCD name.

  Returns:
    A dictionary table of the atoms and bonds for this residue in this residue
    type.
  """
  # The CCD version of 'UNK' is weird. It has a CB and a CG atom. We just want
  # the minimal amino-acid here which is GLY.
  if res_name == 'UNK':
    res_name = 'GLY'
  ccd_data = ccd.get(res_name)
  if not ccd_data:
    raise ValueError(f'Unknown residue type {res_name}')

  keys = (
      '_chem_comp_atom.atom_id',
      '_chem_comp_atom.type_symbol',
      '_chem_comp_bond.atom_id_1',
      '_chem_comp_bond.atom_id_2',
  )

  # Add terminal hydrogens for protonation of the N-terminal
  if res_name == 'PRO':
    res_atoms = {key: [*ccd_data.get(key, [])] for key in keys}
    res_atoms['_chem_comp_atom.atom_id'].extend(['H2', 'H3'])
    res_atoms['_chem_comp_atom.type_symbol'].extend(['H', 'H'])
    res_atoms['_chem_comp_bond.atom_id_1'].extend(['N', 'N'])
    res_atoms['_chem_comp_bond.atom_id_2'].extend(['H2', 'H3'])
  elif res_name in residue_names.PROTEIN_TYPES_WITH_UNKNOWN:
    res_atoms = {key: [*ccd_data.get(key, [])] for key in keys}
    res_atoms['_chem_comp_atom.atom_id'].append('H3')
    res_atoms['_chem_comp_atom.type_symbol'].append('H')
    res_atoms['_chem_comp_bond.atom_id_1'].append('N')
    res_atoms['_chem_comp_bond.atom_id_2'].append('H3')
  else:
    res_atoms = {key: ccd_data.get(key, []) for key in keys}

  return res_atoms


@functools.lru_cache(maxsize=128)
def get_res_atom_names(ccd: chemical_components.Ccd, res_name: str) -> set[str]:
  """Gets the names of the atoms in a given CCD residue."""
  atoms = get_all_atoms_in_entry(ccd, res_name)['_chem_comp_atom.atom_id']
  return set(atoms)
