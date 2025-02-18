#!/usr/bin/python3

from __future__ import print_function

import argparse
import os
import os.path
from collections import namedtuple


import ssg.build_yaml
import ssg.utils
import ssg.environment
import ssg.id_translate
import ssg.build_renumber
import ssg.products


Paths_ = namedtuple("Paths_", ["xccdf", "oval", "ocil", "build_ovals_dir"])


def parse_args():
    parser = argparse.ArgumentParser(
        description="Converts SCAP Security Guide YAML benchmark data "
        "(benchmark, rules, groups) to XCCDF Shorthand Format"
    )
    parser.add_argument(
        "--build-config-yaml", required=True,
        help="YAML file with information about the build configuration. "
        "e.g.: ~/scap-security-guide/build/build_config.yml"
    )
    parser.add_argument(
        "--product-yaml", required=True,
        help="YAML file with information about the product we are building. "
        "e.g.: ~/scap-security-guide/rhel7/product.yml"
    )
    parser.add_argument(
        "--xccdf", required=True,
        help="Output XCCDF file. "
        "e.g.:  ~/scap-security-guide/build/rhel7/ssg-rhel7-xccdf.xml"
    )
    parser.add_argument(
        "--ocil", required=True,
        help="Output OCIL file. "
        "e.g.:  ~/scap-security-guide/build/rhel7/ssg-rhel7-ocil.xml"
    )
    parser.add_argument(
        "--oval", required=True,
        help="Output OVAL file. "
        "e.g.:  ~/scap-security-guide/build/rhel7/ssg-rhel7-oval.xml"
    )
    parser.add_argument(
        "--build-ovals-dir",
        dest="build_ovals_dir",
        help="Directory to store OVAL document for each rule.",
    )
    parser.add_argument(
        "--resolved-base",
        help="To which directory to put processed rule/group/value YAMLs."
    )
    parser.add_argument(
        "--thin-ds-components-dir",
        help="Directory to store XCCDF, OVAL, OCIL, for thin data stream. (off: to disable)"
        "e.g.: ~/scap-security-guide/build/rhel7/thin_ds_component/"
        "Fake profiles are used to create thin DS. Components are generated for each profile.",
    )
    return parser.parse_args()


def link_oval(xccdftree, checks, output_file_name, build_ovals_dir):
    translator = ssg.id_translate.IDTranslator("ssg")
    oval_linker = ssg.build_renumber.OVALFileLinker(
        translator, xccdftree, checks, output_file_name
    )
    oval_linker.build_ovals_dir = build_ovals_dir
    oval_linker.link()
    oval_linker.save_linked_tree()
    oval_linker.link_xccdf()


def link_ocil(xccdftree, checks, output_file_name, ocil):
    translator = ssg.id_translate.IDTranslator("ssg")
    ocil_linker = ssg.build_renumber.OCILFileLinker(
        translator, xccdftree, checks, output_file_name
    )
    ocil_linker.link(ocil)
    ocil_linker.save_linked_tree()
    ocil_linker.link_xccdf()


def link_benchmark(loader, xccdftree, args, benchmark=None):
    checks = xccdftree.findall(".//{%s}check" % ssg.constants.XCCDF12_NS)

    link_oval(xccdftree, checks, args.oval, args.build_ovals_dir)

    ocil = loader.export_ocil_to_xml(benchmark)
    if ocil is not None:
        link_ocil(xccdftree, checks, args.ocil, ocil)

    ssg.xml.ElementTree.ElementTree(xccdftree).write(args.xccdf, encoding="utf-8")


def get_path(path, file_name):
    return os.path.join(path, file_name)


def link_benchmark_per_profile(loader, args):
    if not os.path.exists(args.thin_ds_components_dir):
        os.makedirs(args.thin_ds_components_dir)

    loader.off_ocil = True

    for id_, benchmark in loader.get_benchmark_by_profile():
        xccdftree = benchmark.to_xml_element(loader.env_yaml)
        p = Paths_(
            xccdf=get_path(args.thin_ds_components_dir, "xccdf_{}.xml".format(id_)),
            oval=get_path(args.thin_ds_components_dir, "oval_{}.xml".format(id_)),
            ocil=get_path(args.thin_ds_components_dir, "ocil_{}.xml".format(id_)),
            build_ovals_dir=args.build_ovals_dir
        )
        link_benchmark(loader, xccdftree, p, benchmark)

    loader.off_ocil = False


def main():
    args = parse_args()

    env_yaml = ssg.environment.open_environment(
        args.build_config_yaml, args.product_yaml)
    product_yaml = ssg.products.Product(args.product_yaml)
    base_dir = product_yaml["product_dir"]
    benchmark_root = ssg.utils.required_key(env_yaml, "benchmark_root")

    # we have to "absolutize" the paths the right way, relative to the
    # product_yaml path
    if not os.path.isabs(benchmark_root):
        benchmark_root = os.path.join(base_dir, benchmark_root)

    loader = ssg.build_yaml.LinearLoader(
        env_yaml, args.resolved_base)
    loader.load_compiled_content()
    loader.load_benchmark(benchmark_root)

    loader.add_fixes_to_rules()

    if args.thin_ds_components_dir != "off":
        link_benchmark_per_profile(loader, args)

    xccdftree = loader.export_benchmark_to_xml()
    link_benchmark(loader, xccdftree, args)


if __name__ == "__main__":
    main()
