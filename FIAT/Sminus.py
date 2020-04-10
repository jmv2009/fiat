# Copyright (C) 2019 Cyrus Cheng (Imperial College London)
#
# This file is part of FIAT.
#
# FIAT is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FIAT is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with FIAT. If not, see <http://www.gnu.org/licenses/>.
#
# Modified by David A. Ham (david.ham@imperial.ac.uk), 2019

from sympy import symbols, legendre, Array, diff
import numpy as np
from FIAT.finite_element import FiniteElement
from FIAT.dual_set import make_entity_closure_ids
from FIAT.polynomial_set import mis
from FIAT.reference_element import compute_unflattening_map, flatten_reference_cube

x, y, z = symbols('x y z')
variables = (x, y, z)
leg = legendre


def triangular_number(n):
    return int((n+1)*n/2)

def choose_ijk_total(degree):
    top = 1
    for i in range(1, 2 + degree + 1):
        top = i * top
    bottom = 1
    for i in range(1, degree + 1):
        bottom = i * bottom
    return int(top /(2 * bottom))


class TrimmedSerendipity(FiniteElement):
    def __init__(self, ref_el, degree, mapping):
        if degree < 1:
            raise Exception("Trimmed serendipity elements only valid for k >= 1")

        flat_el = flatten_reference_cube(ref_el)
        dim = flat_el.get_spatial_dimension()
        if dim != 2:
            if dim != 3:
                raise Exception("Trimmed serendipity elements only valid for dimensions 2 and 3")

        flat_topology = flat_el.get_topology()
        entity_ids = {}
        cur = 0

        for top_dim, entities in flat_topology.items():
            entity_ids[top_dim] = {}
            for entity in entities:
                entity_ids[top_dim][entity] = []
        if dim == 2:
            for j in sorted(flat_topology[1]):
                entity_ids[1][j] = list(range(cur, cur + degree))
                cur = cur + degree

            if(degree >= 2):
                entity_ids[2][0] = list(range(cur, cur + 2*triangular_number(degree - 2) + degree))
        
            cur += 2*triangular_number(degree - 2) + degree

        else:
            #3-d case.
            entity_ids[3] = {}
            for j in sorted(flat_topology[1]):
                entity_ids[1][j] = list(range(cur, cur + degree))
                cur = cur + degree
            
            if (degree >= 2 ):
                if (degree < 4):
                    for j in sorted(flat_topology[2]):
                        entity_ids[2][j] = list(range(cur, cur + 2*triangular_number(degree - 2) + degree))
                        cur = cur + 2*triangular_number(degree - 2) + degree
                else:
                    for j in sorted(flat_topology[2]):
                        entity_ids[2][j] = list(range(cur, cur + 3 * degree - 4))
                        cur = cur + 3*degree - 4
            
            
            if (degree >= 4):
                if (degree == 4):
                    entity_ids[3][0] = list(range(cur, cur + 6))
                elif (degree == 5):
                    entity_ids[3][0] = list(range(cur, cur + 11))
                else:
                    interior_ids = 0
                    for i in range(0, degree - 4):
                        interior_ids += 3 * choose_ijk_total(i)
                    entity_ids[3][0] = list(range(cur, cur + 6 + (degree - 4) * 3 + interior_ids))
            else:
                entity_ids[3][0] = list(range(cur, cur))

        formdegree = 1

        entity_closure_ids = make_entity_closure_ids(flat_el, entity_ids)

        super(TrimmedSerendipity, self).__init__(ref_el=ref_el,
                                                 dual=None,
                                                 order=degree,
                                                 formdegree=formdegree,
                                                 mapping=mapping)

        topology = ref_el.get_topology()
        unflattening_map = compute_unflattening_map(topology)
        unflattened_entity_ids = {}
        unflattened_entity_closure_ids = {}

        for dim, entities in sorted(topology.items()):
            unflattened_entity_ids[dim] = {}
            unflattened_entity_closure_ids[dim] = {}
        for dim, entities in sorted(flat_topology.items()):
            for entity in entities:
                unflat_dim, unflat_entity = unflattening_map[(dim, entity)]
                unflattened_entity_ids[unflat_dim][unflat_entity] = entity_ids[dim][entity]
                unflattened_entity_closure_ids[unflat_dim][unflat_entity] = entity_closure_ids[dim][entity]
        self.entity_ids = unflattened_entity_ids
        self.entity_closure_ids = unflattened_entity_closure_ids
        self._degree = degree
        self.flat_el = flat_el

    def degree(self):
        return self._degree

    def get_nodal_basis(self):
        raise NotImplementedError("get_nodal_basis not implemented for trimmed serendipity")

    def get_dual_set(self):
        raise NotImplementedError("get_dual_set is not implemented for trimmed serendipity")

    def get_coeffs(self):
        raise NotImplementedError("get_coeffs not implemented for trimmed serendipity")

    def tabulate(self, order, points, entity=None):

        if entity is None:
            entity = (self.ref_el.get_dimension(), 0)

        entity_dim, entity_id = entity
        transform = self.ref_el.get_entity_transform(entity_dim, entity_id)
        points = list(map(transform, points))

        phivals = {}

        for o in range(order+1):
            alphas = mis(2, o)
            for alpha in alphas:
                try:
                    polynomials = self.basis[alpha]
                except KeyError:
                    polynomials = diff(self.basis[(0, 0)], *zip(variables, alpha))
                    self.basis[alpha] = polynomials
                T = np.zeros((len(polynomials[:, 0]), 2, len(points)))
                for i in range(len(points)):
                    subs = {v: points[i][k] for k, v in enumerate(variables[:2])}
                    for j, f in enumerate(polynomials[:, 0]):
                        T[j, 0, i] = f.evalf(subs=subs)
                    for j, f in enumerate(polynomials[:, 1]):
                        T[j, 1, i] = f.evalf(subs=subs)
                phivals[alpha] = T

        return phivals

    def entity_dofs(self):
        """Return the map of topological entities to degrees of
        freedom for the finite element."""
        return self.entity_ids

    def entity_closure_dofs(self):
        """Return the map of topological entities to degrees of
        freedom on the closure of those entities for the finite element."""
        return self.entity_closure_ids

    def value_shape(self):
        return (2,)

    def dmats(self):
        raise NotImplementedError

    def get_num_members(self, arg):
        raise NotImplementedError

    def space_dimension(self):
        return int(len(self.basis[(0, 0)])/2)


# Splitting the E Lambda function into two seperate functions for E Lambda and E tilde Lambda.
# Correlating with Andrew's paper, leg(j, x_mid) should be a polynomial x^i, leg(j, y_mid) should be y^i,
# dy[0] should represent y-1, dy[1] should represent y+1 (and similar for the dx and x+/- 1).
# Still not sure why we use for loops in only the EL tuple but not the ELTilde tuple.

def e_lambda_1_2d_part_one(deg, dx, dy, x_mid, y_mid):
    EL = tuple(
        [(0, -leg(j, y_mid) * dx[0]) for j in range(deg)] +
        [(0, -leg(j, y_mid) * dx[1]) for j in range(deg)] +
        [(-leg(j, x_mid)*dy[0], 0) for j in range(deg)] +
        [(-leg(j, x_mid)*dy[1], 0) for j in range(deg)])

    return EL


def e_lambda_tilde_1_2d_part_two(deg, dx, dy, x_mid, y_mid):
    ELTilde = tuple([(-leg(deg, x_mid) * dy[0],
                      -leg(deg-1, x_mid) * dx[0] * dx[1] / (deg+1))] +
                    [(-leg(deg, x_mid) * dy[1],
                      leg(deg-1, x_mid) * dx[0] * dx[1] / (deg+1))] +
                    [(-leg(deg-1, y_mid) * dy[0] * dy[1] / (deg+1),
                      -leg(deg, y_mid) * dx[0])] +
                    [(leg(deg-1, y_mid) * dy[0] * dy[1] / (deg+1),
                      -leg(deg, y_mid) * dx[1])])
    return ELTilde


def e_lambda_1_2d(deg, dx, dy, x_mid, y_mid):
    EL = e_lambda_1_2d_part_one(deg, dx, dy, x_mid, y_mid)
    ELTilde = e_lambda_tilde_1_2d_part_two(deg, dx, dy, x_mid, y_mid)

    result = EL + ELTilde
    return result


def determine_f_lambda_portions_2d(deg):
    if (deg < 2):
        DegsOfIteration = []
    else:
        DegsOfIteration = []
        for i in range(2, deg):
            DegsOfIteration += [i]

    return DegsOfIteration


def f_lambda_1_2d_pieces(current_deg, dx, dy, x_mid, y_mid):
    if (current_deg == 2):
        FLpiece = [(leg(0, x_mid) * leg(0, y_mid) * dy[0] * dy[1], 0)]
        FLpiece += [(0, leg(0, x_mid) * leg(0, y_mid) * dx[0] * dx[1])]
    else:
        target_power = current_deg - 2
        FLpiece = tuple([])
        for j in range(0, target_power + 1):
            k = target_power - j
            FLpiece += tuple([(leg(j, x_mid) * leg(k, y_mid) * dy[0] * dy[1], 0)])
            FLpiece += tuple([(0, leg(j, x_mid) * leg(k, y_mid) * dx[0] * dx[1])])
    return FLpiece


def f_lambda_1_2d_trim(deg, dx, dy, x_mid, y_mid):
    DegsOfIteration = determine_f_lambda_portions_2d(deg)
    FL = []
    for i in DegsOfIteration:
        FL += f_lambda_1_2d_pieces(i, dx, dy, x_mid, y_mid)
    return tuple(FL)


def f_lambda_1_2d_tilde(deg, dx, dy, x_mid, y_mid):
    FLTilde = tuple([])
    FLTilde += tuple([(leg(deg - 2, y_mid)*dy[0]*dy[1], 0)])
    FLTilde += tuple([(0, leg(deg - 2, x_mid)*dx[0]*dx[1])])
    for k in range(1, deg - 1):
        FLTilde += tuple([(leg(k, x_mid) * leg(deg - k - 2, y_mid) * dy[0] * dy[1], -leg(k - 1, x_mid) * leg(deg - k - 1, y_mid) * dx[0] * dx[1])])

    return tuple(FLTilde)


def trimmed_f_lambda_2d(deg, dx, dy, x_mid, y_mid):
    FL = f_lambda_1_2d_trim(deg, dx, dy, x_mid, y_mid)
    FLT = f_lambda_1_2d_tilde(deg, dx, dy, x_mid, y_mid)
    result = FL + FLT

    return result


""" def e_lambda_1_3d_part_one(deg, dx, dy, dz, x_mid, y_mid, z_mid):
    EL = tuple(
        [(0, -leg(j, y_mid) * dx[0]) for j in range(deg)] +
        [(0, -leg(j, y_mid) * dx[1]) for j in range(deg)] +
        [(-leg(j, x_mid)*dy[0], 0) for j in range(deg)] +
        [(-leg(j, x_mid)*dy[1], 0) for j in range(deg)])

    return EL """


def e_lambda_1_3d_piece(current_deg, dx, dy, dz, x_mid, y_mid, z_mid):
    ELpiece = tuple([(0, 0, leg(current_deg, z_mid) * dx[0] * dy[1])] +
              [(0, 0, leg(current_deg, z_mid) * dx[1] * dy[1])] +
              [(0, 0, leg(current_deg, z_mid) * dx[1] * dy[0])] +
              [(0, 0, leg(current_deg, z_mid) * dx[0] * dy[0])] +
              [(0, leg(current_deg, y_mid) * dx[0] * dz[1], 0)] +
              [(0, leg(current_deg, y_mid) * dx[1] * dz[1], 0)] +
              [(0, leg(current_deg, y_mid) * dx[1] * dz[0], 0)] +
              [(0, leg(current_deg, y_mid) * dx[0] * dz[0], 0)] +
              [(leg(current_deg, x_mid) * dy[0] * dz[0], 0, 0)] +
              [(leg(current_deg, x_mid) * dy[1] * dz[0], 0, 0)] +
              [(leg(current_deg, x_mid) * dy[1] * dz[1], 0, 0)] +
              [(leg(current_deg, x_mid) * dy[0] * dz[1], 0, 0)])
    return ELpiece

def e_lambda_1_3d_trimmed(max_deg, dx, dy, dz, x_mid, y_mid, z_mid):
    EL = tuple([])
    for i in range(max_deg):
        Elpiece = e_lambda_1_3d_piece(i, dx, dy, dz, x_mid, y_mid, z_mid)
        EL += Elpiece
    return EL

def determine_f_lambda_1_portions_3d(deg):
    if (deg < 2):
        DegsOfIteration = []
    else:
        DegsOfIteration = []
        for i in range(2, deg):
            DegsOfIteration += [i]

    return DegsOfIteration

def f_lambda_1_3d_pieces(current_deg, dx, dy, dz, x_mid, y_mid, z_mid):
    if (current_deg == 2):
        j = 0
        k = 0
        FLpiece = [(leg(j, x_mid) * leg(k, y_mid) * dz[0] * dy[0] * dy[1], 0, 0)]
        FLpiece += [(leg(j, x_mid) * leg(k, y_mid) * dz[1] * dy[0] * dy[1], 0, 0)]
        FLpiece += [(leg(j, x_mid) * leg(k, z_mid) * dy[0] * dz[0] * dz[1], 0, 0)]
        FLpiece += [(leg(j, x_mid) * leg(k, z_mid) * dy[1] * dz[0] * dz[1], 0, 0)]
        FLpiece += [(0, leg(j, y_mid) * leg(k, x_mid) * dz[0] * dx[0] * dx[1], 0)]
        FLpiece += [(0, leg(j, y_mid) * leg(k, x_mid) * dz[1] * dx[0] * dx[1], 0)]
        FLpiece += [(0, leg(j, y_mid) * leg(k, z_mid) * dx[0] * dz[0] * dz[1], 0)]
        FLpiece += [(0, leg(j, y_mid) * leg(k, z_mid) * dx[1] * dz[0] * dz[1], 0)]
        FLpiece += [(0, 0, leg(j, z_mid) * leg(k, y_mid) * dy[0] * dx[0] * dx[1])]
        FLpiece += [(0, 0, leg(j, z_mid) * leg(k, y_mid) * dy[1] * dx[0] * dx[1])]
        FLpiece += [(0, 0, leg(j, z_mid) * leg(k, x_mid) * dx[0] * dy[0] * dy[1])]
        FLpiece += [(0, 0, leg(j, z_mid) * leg(k, x_mid) * dx[1] * dy[0] * dy[1])]
    else:
        target_power = current_deg - 2
        FLpiece = tuple([])
        for j in range(0, target_power + 1):
            k = target_power - j
            FLpiece += tuple([(leg(j, x_mid) * leg(k, y_mid) * dz[0] * dy[0] * dy[1], 0, 0)])
            FLpiece += tuple([(leg(j, x_mid) * leg(k, y_mid) * dz[1] * dy[0] * dy[1], 0, 0)])
            FLpiece += tuple([(leg(j, x_mid) * leg(k, z_mid) * dy[0] * dz[0] * dz[1], 0, 0)])
            FLpiece += tuple([(leg(j, x_mid) * leg(k, z_mid) * dy[1] * dz[0] * dz[1], 0, 0)])
            FLpiece += tuple([(0, leg(j, y_mid) * leg(k, x_mid) * dz[0] * dx[0] * dx[1], 0)])
            FLpiece += tuple([(0, leg(j, y_mid) * leg(k, x_mid) * dz[1] * dx[0] * dx[1], 0)])
            FLpiece += tuple([(0, leg(j, y_mid) * leg(k, z_mid) * dx[0] * dz[0] * dz[1], 0)])
            FLpiece += tuple([(0, leg(j, y_mid) * leg(k, z_mid) * dx[1] * dz[0] * dz[1], 0)])
            FLpiece += tuple([(0, 0, leg(j, z_mid) * leg(k, y_mid) * dy[0] * dx[0] * dx[1])])
            FLpiece += tuple([(0, 0, leg(j, z_mid) * leg(k, y_mid) * dy[1] * dx[0] * dx[1])])
            FLpiece += tuple([(0, 0, leg(j, z_mid) * leg(k, x_mid) * dx[0] * dy[0] * dy[1])])
            FLpiece += tuple([(0, 0, leg(j, z_mid) * leg(k, x_mid) * dx[1] * dy[0] * dy[1])])
    return FLpiece


def f_lambda_1_3d_tilde(max_deg, dx, dy, dz, x_mid, y_mid, z_mid):
    FLtilde = tuple([])
    FLtilde += tuple([(leg(max_deg - 2, y_mid) * dz[0] * dy[0] * dy[1], 0, 0)])
    FLtilde += tuple([(leg(max_deg - 2, y_mid) * dz[1] * dy[0] * dy[1], 0, 0)])
    FLtilde += tuple([(leg(max_deg - 2, z_mid) * dy[0] * dz[0] * dz[1], 0, 0)])
    FLtilde += tuple([(leg(max_deg - 2, z_mid) * dy[1] * dz[0] * dz[1], 0, 0)])
    FLtilde += tuple([(0, leg(max_deg - 2, x_mid) * dz[0] * dx[0] * dx[1], 0)])
    FLtilde += tuple([(0, leg(max_deg - 2, x_mid) * dz[1] * dx[0] * dx[1], 0)])
    FLtilde += tuple([(0, leg(max_deg - 2, z_mid) * dx[0] * dz[0] * dz[1], 0)])
    FLtilde += tuple([(0, leg(max_deg - 2, z_mid) * dx[1] * dz[0] * dz[1], 0)])
    FLtilde += tuple([(0, 0, leg(max_deg - 2, x_mid) * dy[0] * dx[0] * dx[1])])
    FLtilde += tuple([(0, 0, leg(max_deg - 2, x_mid) * dy[1] * dx[0] * dx[1])])
    FLtilde += tuple([(0, 0, leg(max_deg - 2, y_mid) * dx[0] * dy[0] * dy[1])])
    FLtilde += tuple([(0, 0, leg(max_deg - 2, y_mid) * dx[1] * dy[0] * dy[1])])
    for j in range(1, max_deg - 1):
        for k in range(0, 2):
            FLtilde += tuple([(leg(j, x_mid) * leg(max_deg - j - 2, y_mid) * dz[k] * dy[0] * dy[1], 
                               -leg(j-1, x_mid) * leg(max_deg - j - 1, y_mid) * dz[k] * dx[0] * dx[1], 0)])
            FLtilde += tuple([(leg(j, x_mid) * leg(max_deg - j - 2, z_mid) * dy[k] * dz[0] * dz[1], 0, 
                               -leg(j-1, x_mid) * leg(max_deg - j - 1, z_mid) * dy[k] * dx[0] * dx[1])])
            FLtilde += tuple([(0, leg(j, y_mid) * leg(max_deg - j - 2, z_mid) * dx[k] * dz[0] * dz[1], 
                               -leg(j-1, y_mid) * leg(max_deg - j - 1, z_mid) * dx[k] * dy[0] * dy[1])])
    return FLtilde


def f_lambda_1_3d_trim(deg, dx, dy, dz, x_mid, y_mid, z_mid):
    DegsOfIteration = determine_f_lambda_1_portions_3d(deg)
    FL = []
    for i in DegsOfIteration:
        FL += f_lambda_1_3d_pieces(i, dx, dy, dz, x_mid, y_mid, z_mid)
    return tuple(FL)


def trimmed_f_lambda_3d(deg, dx, dy, dz, x_mid, y_mid, z_mid):
    FL = f_lambda_1_3d_trim(deg, dx, dy, dz, x_mid, y_mid, z_mid)
    FLT = f_lambda_1_3d_tilde(deg, dx, dy, dz, x_mid, y_mid, z_mid)
    result = FL + FLT

    return result


def determine_I_lambda_1_portions_3d(deg):
    if (deg < 4):
        DegsOfIteration = []
    else:
        Degs = tuple([])
        DegsOfIteration = tuple([])
        for x in range(0, deg - 3):
            for y in range(0, deg - 3 - x):
                for z in range(0, deg - 3 - x - y):
                    Degs += tuple([(x, y, z)])
        for degs in Degs:
            if(degs[0] + degs[1] + degs[2] == deg - 4):
                DegsOfIteration += tuple([degs])
    return DegsOfIteration


def I_lambda_1_3d(deg, dx, dy, dz, x_mid, y_mid, z_mid):
    DegsOfIteration = determine_I_lambda_1_portions_3d(deg)
    IL = tuple([])
    for Degs in DegsOfIteration:
        IL += tuple([(leg(Degs[0], x_mid) * leg(Degs[1], y_mid) * leg(Degs[2], z_mid) * 
                    dy[0] * dy[1] * dz[0] * dz[1], 0, 0)])
        IL += tuple([(0, leg(Degs[0], x_mid) * leg(Degs[1], y_mid) * leg(Degs[2], z_mid) * 
                    dx[0] * dx[1] * dz[0] * dz[1], 0)])
        IL += tuple([(0, 0, leg(Degs[0], x_mid) * leg(Degs[1], y_mid) * leg(Degs[2], z_mid) * 
                    dy[0] * dy[1] * dy[0] * dy[1])])
    return IL


def I_lambda_1_tilde_3d(deg, dx, dy, dz, x_mid, y_mid, z_mid):
    ILtilde = tuple([])
    ILtilde += tuple([(leg(deg - 4, y_mid) * dy[0] * dy[1] * dz[0] * dz[1], 0, 0)])
    ILtilde += tuple([(leg(deg - 4, z_mid) * dy[0] * dy[1] * dz[0] * dz[1], 0, 0)])
    ILtilde += tuple([(0, leg(deg - 4, x_mid) * dx[0] * dx[1] * dz[0] * dz[1], 0)])
    ILtilde += tuple([(0, leg(deg - 4, z_mid) * dx[0] * dx[1] * dz[0] * dz[1], 0)])
    ILtilde += tuple([(0, 0, leg(deg - 4, x_mid) * dx[0] * dx[1] * dy[0] * dy[1])])
    ILtilde += tuple([(0, 0, leg(deg - 4, y_mid) * dx[0] * dx[1] * dy[0] * dy[1])])
    for j in range(1, deg - 3):
        ILtilde += tuple([(leg(j, x_mid) * leg(deg - j - 4, y_mid) * dy[0] * dy[1] * dz[0] * dz[1],
                           -leg(j - 1, x_mid) * leg(deg - j - 3, y_mid) * dx[0] * dx[1] * dz[0] * dz[1], 0)])
        ILtilde += tuple([(leg(j, x_mid) * leg(deg - j - 4, z_mid) * dy[0] * dy[1] * dz[0] * dz[1], 0,
                           -leg(j - 1, x_mid) * leg(deg - j - 3, z_mid) * dx[0] * dx[1] * dy[0] * dy[1])])
        if(deg > 5):
            ILtilde += tuple([(0, leg(j, y_mid) * leg(deg - j - 4, z_mid) * dx[0] * dx[1] * dz[0] * dz[1],
                               -leg(j - 1, y_mid) * leg(deg - j - 3, z_mid) * dx[0] * dx[1] * dy[0] * dy[1])])
    return ILtilde       


#This is always 1-forms regardless of 2 or 3 dimensions.
class TrimmedSerendipityEdge(TrimmedSerendipity):
    def __init__(self, ref_el, degree):
        if degree < 1:
            raise Exception("Trimmed Serendipity_k edge elements only valid for k >= 1")

        flat_el = flatten_reference_cube(ref_el)
        dim = flat_el.get_spatial_dimension()
        if dim != 2:
            if dim != 3:
                raise Exception("Trimmed Serendipity_k edge elements only valid for dimensions 2 and 3")

        verts = flat_el.get_vertices()

        dx = ((verts[-1][0] - x)/(verts[-1][0] - verts[0][0]), (x - verts[0][0])/(verts[-1][0] - verts[0][0]))
        dy = ((verts[-1][1] - y)/(verts[-1][1] - verts[0][1]), (y - verts[0][1])/(verts[-1][1] - verts[0][1]))
        x_mid = 2*x-(verts[-1][0] + verts[0][0])
        y_mid = 2*y-(verts[-1][1] + verts[0][1])
        try:
            dz = ((verts[-1][2] - z)/(verts[-1][2] - verts[0][2]), (z - verts[0][2])/(verts[-1][2] - verts[0][2]))
            z_mid = 2*z-(verts[-1][2] + verts[0][2])
        except IndexError:
            dz = None
            z_mid = None

        if dim == 2:
            EL = e_lambda_1_2d_part_one(degree, dx, dy, x_mid, y_mid)
        else:
            EL = e_lambda_1_3d_trimmed(degree, dx, dy, dz, x_mid, y_mid, z_mid)
        if degree >= 2:
            if dim == 2:
                FL = trimmed_f_lambda_2d(degree, dx, dy, x_mid, y_mid)
            else:
                FL = trimmed_f_lambda_3d(degree, dx, dy, dz, x_mid, y_mid, z_mid)
        else:
            FL = ()
        if dim == 3:
            if degree >= 4:
                IL = I_lambda_1_3d(degree, dx, dy, dz, x_mid, y_mid, z_mid) + I_lambda_1_tilde_3d(degree, dx, dy,
                                                                                                  dz, x_mid,
                                                                                                  y_mid, z_mid)
            else:
                IL = ()
        
        Sminus_list = EL + FL
        if dim == 3:
            Sminus_list = Sminus_list + IL
        
        self.basis = {(0, 0): Array(Sminus_list)}
        super(TrimmedSerendipityEdge, self).__init__(ref_el=ref_el, degree=degree, mapping="covariant piola")


#This is 1 forms in 2d (rotated) and 2 forms in 3d (not just a rotation)
class TrimmedSerendipityFace(TrimmedSerendipity):
    def __init__(self, ref_el, degree):
        if degree < 1:
            raise Exception("Trimmed serendipity face elements only valid for k >= 1")

        flat_el = flatten_reference_cube(ref_el)
        dim = flat_el.get_spatial_dimension()
        if dim != 2:
            if dim != 3:
                raise Exception("Trimmed serendipity face elements only valid for dimensions 2 and 3")

        verts = flat_el.get_vertices()

        dx = ((verts[-1][0] - x)/(verts[-1][0] - verts[0][0]), (x - verts[0][0])/(verts[-1][0] - verts[0][0]))
        dy = ((verts[-1][1] - y)/(verts[-1][1] - verts[0][1]), (y - verts[0][1])/(verts[-1][1] - verts[0][1]))
        x_mid = 2*x-(verts[-1][0] + verts[0][0])
        y_mid = 2*y-(verts[-1][1] + verts[0][1])
        try:
            dz = ((verts[-1][2] - z)/(verts[-1][2] - verts[0][2]), (z - verts[0][2])/(verts[-1][2] - verts[0][2]))
            z_mid = 2*z-(verts[-1][2] + verts[0][2])
        except IndexError:
            dz = None
            z_mid = None
        
        if (dim == 2):
            EL = e_lambda_1_2d_part_one(degree, dx, dy, x_mid, y_mid)
        else:
            EL = e_lambda_1_3d_trimmed(degree, dx, dy, dz, x_mid, y_mid, z_mid)
        if degree >= 2:
            if dim == 2:
                FL = trimmed_f_lambda_2d(degree, dx, dy, x_mid, y_mid)
            else:
                FL = trimmed_f_lambda_3d(degree, dx, dy, dz, x_mid, y_mid, z_mid)
        else:
            FL = ()
        if dim == 3:
            if degree >= 4:
                IL = I_lambda_1_3d(degree, dx, dy, dz, x_mid, y_mid, z_mid) + I_lambda_1_tilde_3d(degree, dx, dy, 
                                                                                                  dz, x_mid,
                                                                                                  y_mid, z_mid)
            else:
                IL = ()

        bdmcf_list = EL + FL + IL
        bdmcf_list = [[-a[1], a[0]] for a in bdmcf_list]
        self.basis = {(0, 0): Array(bdmcf_list)}
        super(TrimmedSerendipityFace, self).__init__(ref_el=ref_el, degree=degree, mapping="contravariant piola")