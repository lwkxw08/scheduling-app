import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import TextAlign from '@tiptap/extension-text-align';
import Underline from '@tiptap/extension-underline';
import { TextStyle } from '@tiptap/extension-text-style';
import Color from '@tiptap/extension-color';
import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { 
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  AlignLeft, AlignCenter, AlignRight, AlignJustify,
  List, ListOrdered, Link as LinkIcon, Image as ImageIcon,
  Undo, Redo, Code, Quote, Heading1, Heading2, Heading3,
  Palette
} from 'lucide-react';

interface RichTextEditorProps {
  content: string;
  onChange: (html: string) => void;
  placeholder?: string;
  className?: string;
}

const MenuBar = ({ editor }: { editor: ReturnType<typeof useEditor> }) => {
  if (!editor) {
    return null;
  }

  const addLink = () => {
    const url = window.prompt('Enter URL:');
    if (url) {
      editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
    }
  };

  const addImage = () => {
    const url = window.prompt('Enter image URL:');
    if (url) {
      editor.chain().focus().setImage({ src: url }).run();
    }
  };

  const setColor = () => {
    const color = window.prompt('Enter color (e.g., #ff0000 or red):');
    if (color) {
      editor.chain().focus().setColor(color).run();
    }
  };

  return (
    <div className="flex flex-wrap gap-1 p-2 border-b bg-gray-50 rounded-t-lg">
      <Button
        type="button"
        variant={editor.isActive('bold') ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleBold().run()}
        className="h-8 w-8 p-0"
        title="Bold"
      >
        <Bold className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive('italic') ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleItalic().run()}
        className="h-8 w-8 p-0"
        title="Italic"
      >
        <Italic className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive('underline') ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleUnderline().run()}
        className="h-8 w-8 p-0"
        title="Underline"
      >
        <UnderlineIcon className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive('strike') ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleStrike().run()}
        className="h-8 w-8 p-0"
        title="Strikethrough"
      >
        <Strikethrough className="h-4 w-4" />
      </Button>

      <div className="w-px h-8 bg-gray-300 mx-1" />

      <Button
        type="button"
        variant={editor.isActive('heading', { level: 1 }) ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        className="h-8 w-8 p-0"
        title="Heading 1"
      >
        <Heading1 className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive('heading', { level: 2 }) ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        className="h-8 w-8 p-0"
        title="Heading 2"
      >
        <Heading2 className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive('heading', { level: 3 }) ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        className="h-8 w-8 p-0"
        title="Heading 3"
      >
        <Heading3 className="h-4 w-4" />
      </Button>

      <div className="w-px h-8 bg-gray-300 mx-1" />

      <Button
        type="button"
        variant={editor.isActive({ textAlign: 'left' }) ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().setTextAlign('left').run()}
        className="h-8 w-8 p-0"
        title="Align Left"
      >
        <AlignLeft className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive({ textAlign: 'center' }) ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().setTextAlign('center').run()}
        className="h-8 w-8 p-0"
        title="Align Center"
      >
        <AlignCenter className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive({ textAlign: 'right' }) ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().setTextAlign('right').run()}
        className="h-8 w-8 p-0"
        title="Align Right"
      >
        <AlignRight className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive({ textAlign: 'justify' }) ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().setTextAlign('justify').run()}
        className="h-8 w-8 p-0"
        title="Justify"
      >
        <AlignJustify className="h-4 w-4" />
      </Button>

      <div className="w-px h-8 bg-gray-300 mx-1" />

      <Button
        type="button"
        variant={editor.isActive('bulletList') ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        className="h-8 w-8 p-0"
        title="Bullet List"
      >
        <List className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive('orderedList') ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        className="h-8 w-8 p-0"
        title="Numbered List"
      >
        <ListOrdered className="h-4 w-4" />
      </Button>

      <div className="w-px h-8 bg-gray-300 mx-1" />

      <Button
        type="button"
        variant={editor.isActive('blockquote') ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        className="h-8 w-8 p-0"
        title="Quote"
      >
        <Quote className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={editor.isActive('code') ? 'default' : 'ghost'}
        size="sm"
        onClick={() => editor.chain().focus().toggleCode().run()}
        className="h-8 w-8 p-0"
        title="Code"
      >
        <Code className="h-4 w-4" />
      </Button>

      <div className="w-px h-8 bg-gray-300 mx-1" />

      <Button
        type="button"
        variant={editor.isActive('link') ? 'default' : 'ghost'}
        size="sm"
        onClick={addLink}
        className="h-8 w-8 p-0"
        title="Add Link"
      >
        <LinkIcon className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={addImage}
        className="h-8 w-8 p-0"
        title="Add Image"
      >
        <ImageIcon className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={setColor}
        className="h-8 w-8 p-0"
        title="Text Color"
      >
        <Palette className="h-4 w-4" />
      </Button>

      <div className="w-px h-8 bg-gray-300 mx-1" />

      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
        className="h-8 w-8 p-0"
        title="Undo"
      >
        <Undo className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
        className="h-8 w-8 p-0"
        title="Redo"
      >
        <Redo className="h-4 w-4" />
      </Button>
    </div>
  );
};

export function RichTextEditor({ content, onChange, placeholder, className }: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-blue-600 underline',
        },
      }),
      Image.configure({
        HTMLAttributes: {
          class: 'max-w-full h-auto',
        },
      }),
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      TextStyle,
      Color,
    ],
    content: content,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    },
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none min-h-48 p-4 focus:outline-none',
      },
    },
  });

  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content);
    }
  }, [content, editor]);

  return (
    <div className={`border rounded-lg overflow-hidden relative ${className || ''}`}>
      <MenuBar editor={editor} />
      <div className="relative">
        <EditorContent editor={editor} />
        {!content && placeholder && (
          <div className="absolute top-4 left-4 text-gray-400 pointer-events-none">
            {placeholder}
          </div>
        )}
      </div>
    </div>
  );
}

export function insertPlaceholderIntoEditor(editor: ReturnType<typeof useEditor>, placeholder: string) {
  if (editor) {
    editor.chain().focus().insertContent(placeholder).run();
  }
}
