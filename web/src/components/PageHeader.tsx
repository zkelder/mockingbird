import type { ReactNode, RefObject } from "react";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  // Place Story Deep Dives & Representative Evidence v1: lets a page that
  // swaps its own *subject* in place (a Taxon/Feature Story page reused for
  // a different taxon/Feature id without a full remount) move focus to its
  // own heading on that change -- the same WAI-ARIA "focus the new region's
  // own heading" pattern Fast Review/the mobile nav drawer already use
  // (`tabIndex={-1}` makes the heading programmatically focusable without
  // adding it to the normal Tab order). Optional and unused by every
  // pre-existing caller -- purely additive.
  headingRef?: RefObject<HTMLHeadingElement | null>;
}

export function PageHeader({ eyebrow, title, description, actions, headingRef }: PageHeaderProps) {
  return (
    <div className="page-header">
      <div>
        {eyebrow ? <span className="page-eyebrow">{eyebrow}</span> : null}
        <h1 ref={headingRef} tabIndex={headingRef ? -1 : undefined}>
          {title}
        </h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-header-actions">{actions}</div> : null}
    </div>
  );
}
