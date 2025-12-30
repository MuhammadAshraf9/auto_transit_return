from odoo import models
import logging

_logger = logging.getLogger(__name__)


class StockBackorderConfirmation(models.TransientModel):
    _inherit = "stock.backorder.confirmation"

    def _get_root_source_location(self, move):
        """Get original source location before any transit/moves"""
        while move.move_orig_ids:
            move = move.move_orig_ids[0]
        return move.location_id

    def process_cancel_backorder(self):
        res = super().process_cancel_backorder()

        pickings = self.pick_ids.filtered(
            lambda p:
            p.state == "done"
            and p.picking_type_id.code == "internal"
            and p.location_id.usage == "transit"
        )

        for picking in pickings:
            return_lines = []
            original_source_location = False

            for move in picking.move_ids.filtered(lambda m: m.state == "done"):
                demanded = move.product_uom_qty
                done = sum(move.move_line_ids.mapped("quantity"))
                diff_qty = demanded - done

                if diff_qty <= 0:
                    continue

                original_source_location = self._get_root_source_location(move)

                return_lines.append((0, 0, {
                    "product_id": move.product_id.id,
                    "quantity": diff_qty,
                }))

            if not return_lines or not original_source_location:
                continue

            return_wizard = self.env["stock.return.picking"].create({
                "picking_id": picking.id,
                "product_return_moves": return_lines,
            })

            return_picking = return_wizard._create_return()

            return_picking.write({
                "location_id": picking.location_id.id,  # Transit
                "location_dest_id": original_source_location.id,  # Original Source
                "state": "draft",
            })

        return res