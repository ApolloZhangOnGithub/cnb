'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import type { PageTree } from 'fumadocs-core/page-tree';

function NavItem({ item, basePath }: { item: PageTree.Item; basePath: string }) {
  const pathname = usePathname();
  const itemUrl = item.url;
  const href = itemUrl.startsWith(basePath) ? itemUrl : `${basePath}${itemUrl}`;
  const pathWithoutBase = pathname;
  const urlWithoutBase = itemUrl.startsWith(basePath) ? itemUrl.slice(basePath.length) : itemUrl;
  const isActive = pathWithoutBase === urlWithoutBase || pathWithoutBase === `${urlWithoutBase}/`;

  return (
    <Link
      href={urlWithoutBase}
      data-active={isActive}
      className={`sidebar-item ${isActive ? 'sidebar-item-active' : ''}`}
    >
      {item.name}
    </Link>
  );
}

function NavFolder({ node, basePath }: { node: PageTree.Folder; basePath: string }) {
  return (
    <div className="sidebar-section">
      <div className="sidebar-section-title">{node.name}</div>
      <div className="sidebar-section-items">
        {node.children.map((child, i) => {
          if (child.type === 'page') {
            return <NavItem key={i} item={child} basePath={basePath} />;
          }
          if (child.type === 'folder') {
            return <NavFolder key={i} node={child} basePath={basePath} />;
          }
          return null;
        })}
      </div>
    </div>
  );
}

export function CustomSidebar({ tree, basePath = '/docs' }: { tree: PageTree.Root; basePath?: string }) {
  return (
    <aside className="custom-sidebar">
      <div className="sidebar-search">
        <div className="sidebar-search-box">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <span>搜索文档</span>
          <kbd>⌘K</kbd>
        </div>
      </div>
      <nav className="sidebar-nav">
        {tree.children.map((child, i) => {
          if (child.type === 'page') {
            return null;
          }
          if (child.type === 'folder') {
            return <NavFolder key={i} node={child} basePath={basePath} />;
          }
          return null;
        })}
      </nav>
    </aside>
  );
}
