"""
Built-in plugins for RDF, DTDL, and CDM formats.

JSON-LD support now flows through the rdflib-backed RDF pipeline,
so no standalone JSON-LD plugin is provided.
"""

from .rdf_plugin import RDFPlugin
from .dtdl_plugin import DTDLPlugin
from .cdm_plugin import CDMPlugin

__all__ = ["RDFPlugin", "DTDLPlugin", "CDMPlugin"]
