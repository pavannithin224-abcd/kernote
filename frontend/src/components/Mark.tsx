/**
 * The Kernote mark — a K whose upper arm is whole and whose lower arm is
 * broken: a verified claim, and the same claim after the code moved under it.
 *
 * `currentColor` throughout, so it takes the colour of whatever it sits in and
 * needs no light and dark variants. Below 24px the gap in the lower arm falls
 * under a pixel and reads as a rendering fault, so small sizes get the solid
 * arm instead. Source and rationale: `design/logo/`.
 */
export function Mark({ size = 20, solid }: { size?: number; solid?: boolean }) {
  const broken = !(solid ?? size < 24)
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth={5}
      role="img"
      aria-label="Kernote"
      className="shrink-0"
    >
      <path d="M14 10 V 38" />
      <path d="M16 24 L 35 11" />
      {broken ? (
        <>
          <path d="M16 24 L 24.8 30.02" />
          <path d="M28.1 32.28 L 35 37" />
        </>
      ) : (
        <path d="M16 24 L 35 37" />
      )}
    </svg>
  )
}
