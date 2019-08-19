"""Jedi Language Server

Creates the language server constant and wraps "features" with it.

Official language server spec:
    https://microsoft.github.io/language-server-protocol/specification
"""

from typing import List, Optional

from pygls.server import LanguageServer
from pygls.features import (
    COMPLETION,
    DEFINITION,
    HOVER,
    REFERENCES,
    RENAME,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
)
from pygls.types import (
    CompletionItem,
    CompletionList,
    CompletionParams,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    Hover,
    Location,
    RenameParams,
    TextDocumentPositionParams,
    TextDocumentSyncKind,
    TextEdit,
    WorkspaceEdit,
)

from .type_map import get_lsp_type

from .server_utils import get_jedi_script, locations_from_definitions


SERVER = LanguageServer()

# NOTE: neovim LanguageClient doesn't support incremental completions. When it
# does, I may consider relaxing this constraint
SERVER.sync_kind = TextDocumentSyncKind.FULL


@SERVER.feature(COMPLETION, triggerCharacters=["."])
def lsp_completion(server: LanguageServer, params: CompletionParams = None):
    """Returns completion items."""
    script = get_jedi_script(server, params)
    jedi_completions = script.completions()
    return CompletionList(
        is_incomplete=False,
        items=[
            CompletionItem(
                label=completion.name,
                kind=get_lsp_type(completion.type),
                detail=completion.description,
                documentation=completion.docstring(),
                insert_text=completion.name,
            )
            for completion in jedi_completions
        ],
    )


@SERVER.feature(DEFINITION)
def lsp_definition(
    server: LanguageServer, params: TextDocumentPositionParams
) -> List[Location]:
    """Support Goto Definition"""
    script = get_jedi_script(server, params)
    definitions = script.goto_assignments(
        follow_imports=True, follow_builtin_imports=True
    )
    return locations_from_definitions(definitions)


@SERVER.feature(HOVER)
def lsp_hover(
    server: LanguageServer, params: TextDocumentPositionParams
) -> Hover:
    """Support the hover feature"""
    script = get_jedi_script(server, params)
    definitions = script.goto_definitions()
    return Hover(
        contents=(
            definitions[0].docstring()
            if definitions
            else "No docstring definition found."
        )
    )


@SERVER.feature(REFERENCES)
def lsp_references(
    server: LanguageServer, params: TextDocumentPositionParams
) -> List[Location]:
    """Obtain all references to document"""
    script = get_jedi_script(server, params)
    definitions = script.usages()
    return locations_from_definitions(definitions)


@SERVER.feature(RENAME)
def lsp_rename(
    server: LanguageServer, params: RenameParams
) -> Optional[WorkspaceEdit]:
    """Optional workspace edit"""
    script = get_jedi_script(server, params)
    definitions = script.usages()
    locations = locations_from_definitions(definitions)
    if not locations:
        return None
    changes = {}
    for location in locations:
        text_edit = TextEdit(location.range, new_text=params.newName)
        if location.uri not in changes:
            changes[location.uri] = [text_edit]
        else:
            changes[location.uri].append(text_edit)
    return WorkspaceEdit(changes=changes)


@SERVER.feature(TEXT_DOCUMENT_DID_CHANGE)
def lsp_did_change(
    server: LanguageServer, params: DidChangeTextDocumentParams
) -> None:
    """Updates file when the file changes on server"""
    workspace = server.workspace
    if params.contentChanges:
        for change in params.contentChanges:
            workspace.update_document(
                text_doc=params.textDocument, change=change
            )


@SERVER.feature(TEXT_DOCUMENT_DID_OPEN)
def lsp_did_open(
    server: LanguageServer, params: DidOpenTextDocumentParams
) -> None:
    """Text document did, in fact, open"""
    workspace = server.workspace
    workspace.put_document(params.textDocument)
