import argparse
import sys

from report import VALID_OUTPUT_FORMATS, VALID_SECTIONS, render_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="Orbital mechanics simulator and space exploration report."
    )
    parser.add_argument(
        "--section",
        choices=VALID_SECTIONS,
        default="all",
        help="Select which section to display.",
    )
    parser.add_argument(
        "--format",
        choices=VALID_OUTPUT_FORMATS,
        default="text",
        help="Select report output format.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output file path. If omitted, prints to stdout.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    report_body = render_report(args.section, args.format)

    if args.output is not None:
        try:
            with open(args.output, "w", encoding="utf-8") as output_file:
                output_file.write(report_body + "\n")
        except OSError as e:
            print(f"Error: could not write to '{args.output}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Report written to {args.output}")
    else:
        print(report_body)


if __name__ == "__main__":
    main()
