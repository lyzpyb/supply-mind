"""
Multi-Echelon Inventory Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.inventory.multi_echelon.main import InventoryMultiEchelon
from supplymind.skills.inventory.multi_echelon.schema import MultiEchelonInput, EchelonNode


@click.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="JSON file with network config")
@click.option("--service-level", "-sl", default=0.95, type=float, help="Target service level (default: 0.95)")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path")
def inventory_multi_echelon(config: str | None, service_level: float, output: str | None):
    """Optimize multi-echelon inventory safety stock placement.

    Example:
        supplymind inventory-multi-echelon --config network.json --service-level 0.95
    """
    nodes = []
    if config:
        try:
            with open(config, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes_data = data.get("nodes", [])
            for nd in nodes_data:
                nodes.append(EchelonNode(**nd))
        except Exception as e:
            click.echo(f"Error loading config: {e}", err=True)
            sys.exit(1)
    else:
        # Demo network
        click.echo("No config provided; using demo 3-node network.")
        nodes = [
            EchelonNode(node_id="FACTORY", name="Central Factory", type="factory",
                        demand_mean=500, demand_std=80, lead_time_days=0),
            EchelonNode(node_id="DC_NORTH", name="North DC", type="dc", parent_id="FACTORY",
                        demand_mean=200, demand_std=40, lead_time_days=3),
            EchelonNode(node_id="DC_SOUTH", name="South DC", type="dc", parent_id="FACTORY",
                        demand_mean=300, demand_std=60, lead_time_days=4),
            EchelonNode(node_id="STORE_A1", name="Store A1", type="store", parent_id="DC_NORTH",
                        demand_mean=80, demand_std=20, lead_time_days=2),
            EchelonNode(node_id="STORE_A2", name="Store A2", type="store", parent_id="DC_NORTH",
                        demand_mean=120, demand_std=30, lead_time_days=1),
            EchelonNode(node_id="STORE_B1", name="Store B1", type="store", parent_id="DC_SOUTH",
                        demand_mean=150, demand_std=35, lead_time_days=2),
            EchelonNode(node_id="STORE_B2", name="Store B2", type="store", parent_id="DC_SOUTH",
                        demand_mean=150, demand_std=35, lead_time_days=2),
        ]

    params = MultiEchelonInput(nodes=nodes, target_service_level=service_level)
    skill = InventoryMultiEchelon()
    result = skill.run(params)

    output_dict = result.model_dump()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        click.echo(f"Multi-echelon analysis saved to {output}")
    else:
        _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 72)
    click.echo("  SupplyMind - Multi-Echelon Inventory Analysis")
    click.echo("=" * 72)
    click.echo()

    s = result.summary
    ns = s.get("network_structure", {})
    click.echo(f"  Network:              {ns.get('factories', 0)} factories, "
               f"{ns.get('dcs', 0)} DCs, {ns.get('stores', 0)} stores")
    click.echo(f"  Target SL:            {s.get('target_service_level', 0):.1%}")
    click.echo(f"  Avg Achieved SL:      {s.get('avg_achieved_sl', 0):.1%}")
    click.echo(f"  System-wide SS:       {s.get('total_system_safety_stock', 0):,.1f} units")
    click.echo()

    if result.results:
        click.echo("  Node Details:")
        click.echo("  " + "-" * 70)
        click.echo(f"  {'Node':<18} {'Type':<8} {'LocalSS':>9} {'EchelonSS':>10} {'TotalSS':>9} {'ROP':>10} {'SL':>7}")
        click.echo("  " + "-" * 70)

        for r in result.results:
            click.echo(
                f"  {r.name:<17} {r.type:<8} {r.local_ss:>9.1f} "
                f"{r.echelon_ss:>10.1f} {r.total_ss:>9.1f} "
                f"{r.reorder_point:>10.1f} {r.service_level_achieved:>6.1%}"
            )

    click.echo()
    click.echo("=" * 72)


if __name__ == "__main__":
    inventory_multi_echelon()
