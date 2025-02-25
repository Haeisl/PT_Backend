# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys

sys.path.insert(0, os.path.abspath("../.."))
sys.path.insert(0, os.path.abspath("../../Docker_Sim"))
sys.path.insert(0, os.path.abspath("../../utils"))
sys.path.insert(0, os.path.abspath("../../process_simulations"))

project = 'Epilepsy Planning Tool - Backend'
copyright = '2025, David Hasse, Jan-Vincent Mock, Aleksandr Udalov'
author = 'David Hasse, Jan-Vincent Mock, Aleksandr Udalov'
release = '27.02.2025'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',      # for autodoc
    'sphinx.ext.napoleon',     # if using Google or NumPy style docstrings
    'sphinx.ext.viewcode',     # optional extension to link to your code
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "private-members": True
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
