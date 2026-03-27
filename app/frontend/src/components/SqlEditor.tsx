import React, { useRef, useImperativeHandle, forwardRef } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { useTheme } from '@mui/material';

export interface SqlEditorHandle {
  insertAtCursor: (text: string) => void;
}

interface SqlEditorProps {
  value: string;
  onChange: (value: string) => void;
  onExecute: () => void;
}

const SqlEditor = forwardRef<SqlEditorHandle, SqlEditorProps>(
  function SqlEditor({ value, onChange, onExecute }, ref) {
    const theme = useTheme();
    const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

    useImperativeHandle(ref, () => ({
      insertAtCursor(text: string) {
        const editor = editorRef.current;
        if (!editor) return;
        const position = editor.getPosition();
        if (!position) return;
        editor.executeEdits('resource-browser', [
          { range: { startLineNumber: position.lineNumber, startColumn: position.column, endLineNumber: position.lineNumber, endColumn: position.column }, text },
        ]);
        editor.focus();
      },
    }));

    const handleMount: OnMount = (editor, monaco) => {
      editorRef.current = editor;
      editor.addAction({
        id: 'execute-query',
        label: 'Execute Query',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
        run: () => onExecute(),
      });
      editor.focus();
    };

    return (
      <Editor
        height="280px"
        language="sql"
        theme={theme.palette.mode === 'dark' ? 'vs-dark' : 'light'}
        value={value}
        onChange={(v) => onChange(v ?? '')}
        onMount={handleMount}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          wordWrap: 'on',
          automaticLayout: true,
          padding: { top: 8, bottom: 8 },
          tabSize: 2,
        }}
      />
    );
  }
);

export default SqlEditor;
